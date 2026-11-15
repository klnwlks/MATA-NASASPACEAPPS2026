"""Classify every Sentinel-1 acquisition over Bay on both tracks into dry / water / flood, per 10 m pixel.

Inputs (all streamed as small windows, nothing large lands on disk):
  - Planetary Computer `sentinel-1-rtc` (gamma0, terrain corrected with GLO-30), VV only, 2024-11-15 to 2026-11-15:
    descending track 32 (S1A until 2026-06, S1C from 2025-07, S1D from 2026-04: 12-day, then mostly 6-day revisit)
    and ascending track 142 (S1C from 2025-04, S1D in 2026: 12-day).
  - history.py: per-pixel, per-month median and spread of the same track over the four years before the window.
  - Copernicus Data Space catalogue: the full list of acquisitions, so dates acquired but absent from the
    RTC collection are recorded as missing rather than silently dropped.
  - Copernicus GLO-30 (slope mask) and ESA WorldCover 2021 (cropland and wetland; low confidence unless lake-connected).
Method: a pixel floods when it is water on this pass (per-pass Otsu threshold) and either connected to the lake and 3 dB
darker than the dry season, or unusually dark for its track and
calendar month over the four-year history (z <= Z_THR). Each track keeps its own references, so viewing geometries
never mix. The same classification is repeated with looser and stricter thresholds to give hectare ranges.
Run after boundaries.py and history.py: .venv/bin/python scripts/floods.py [track ...]
Output: /tmp/mata-floods/classes.npz (uint8 class stack + grid, bit-packed loose/strict flood masks), read by flood_summary.py.
"""
import json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np, rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds
from scipy.ndimage import gaussian_filter, label, uniform_filter

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["GDAL_HTTP_MAX_RETRY"] = "5"
START, END = "2024-11-15", "2026-11-15"
TRACKS = {32: "descending", 142: "ascending"}
PC = "https://planetarycomputer.microsoft.com/api"
CDSE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?"
DEM = "/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N14_00_E121_00_DEM/Copernicus_DSM_COG_10_N14_00_E121_00_DEM.tif"
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif"
OUT = "/tmp/mata-floods"
BUFFER_DEG, PX = 0.01, 10.31  # Web Mercator metres per pixel, about 10 m on the ground at 14.1 N
Z_THR, DROP_DB, MAX_SLOPE_DEG, PERMANENT_SHARE = -2.0, 3.0, 5.0, 0.8
# Sensitivity for hectare ranges: (water threshold shift dB, z threshold, dry-season drop dB) for loose and strict.
LOOSE, STRICT = (1.0, -1.5, 2.0), (-1.0, -2.5, 4.0)
DEM_SMOOTH_PX = 6  # about 60 m, as in terrain.py
# Classes. Low-confidence water: cropland or wetland not connected to the lake, where paddies look like water outside any flood.
# Radar-blind: built-up or tree cover, where C-band sees walls and canopy, not the water around them (unknown, never dry).
NODATA, DRY, PERMANENT, FLOOD, FLOOD_LOW, BLIND = 0, 1, 2, 3, 4, 5


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def grid():
    xs, ys = [], []
    for f in json.load(open("public/data/barangays.geojson"))["features"]:
        for ring in (f["geometry"]["coordinates"] if f["geometry"]["type"] == "Polygon" else [r for p in f["geometry"]["coordinates"] for r in p]):
            xs += [c[0] for c in ring]; ys += [c[1] for c in ring]
    w, s, e, n = transform_bounds("EPSG:4326", "EPSG:3857", min(xs) - BUFFER_DEG, min(ys) - BUFFER_DEG, max(xs) + BUFFER_DEG, max(ys) + BUFFER_DEG)
    return from_origin(w, n, PX, PX), (int((n - s) / PX), int((e - w) / PX))


def warp(src_path, transform, shape, resampling=Resampling.bilinear, dtype="float32", tries=5):
    # Hour-long streams of hundreds of windows meet DNS blips and dropped connections; one must not end the run.
    for attempt in range(tries):
        try:
            return _warp(src_path, transform, shape, resampling, dtype)
        except rasterio.errors.RasterioIOError:
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))


def _warp(src_path, transform, shape, resampling, dtype):
    dst = np.full(shape, np.nan if dtype == "float32" else 0, dtype)
    with rasterio.open(src_path) as src:
        b = transform_bounds("EPSG:3857", src.crs, transform.c, transform.f - shape[0] * PX, transform.c + shape[1] * PX, transform.f)
        win = from_bounds(*b, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win, boundless=True, fill_value=0).astype(dtype)
        if dtype == "float32":
            a[a <= 0] = np.nan
        reproject(a, dst, src_transform=src.window_transform(win), src_crs=src.crs, dst_transform=transform, dst_crs="EPSG:3857", resampling=resampling, src_nodata=np.nan if dtype == "float32" else None)
    return dst


def to_db(a, k=5):  # boxcar despeckle in linear power, then dB
    ok = np.isfinite(a)
    num, den = uniform_filter(np.where(ok, a, 0), k), uniform_filter(ok.astype("float32"), k)
    return np.where(ok, 10 * np.log10(np.maximum(num, 1e-6) / np.maximum(den, 1e-6)), np.nan).astype("float32")


def otsu(x):
    h, edges = np.histogram(x[np.isfinite(x)], 200)
    c = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(h); w1 = w0[-1] - w0
    m0 = np.cumsum(h * c) / np.maximum(w0, 1); m1 = (np.sum(h * c) - np.cumsum(h * c)) / np.maximum(w1, 1)
    return float(c[np.argmax(w0 * w1 * (m0 - m1) ** 2)])


def acquisitions(track):
    flt = (f"Collection/Name eq 'SENTINEL-1' and OData.CSC.Intersects(area=geography'SRID=4326;POINT(121.265 14.15)') and "
           "Attributes/OData.CSC.StringAttribute/any(a:a/Name eq 'productType' and a/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S') and "
           f"Attributes/OData.CSC.IntegerAttribute/any(a:a/Name eq 'relativeOrbitNumber' and a/OData.CSC.IntegerAttribute/Value eq {track}) and "
           f"ContentDate/Start gt {START}T00:00:00.000Z and ContentDate/Start lt {END}T00:00:00.000Z")
    names = [p["Name"] for p in get(CDSE + urllib.parse.urlencode({"$filter": flt, "$top": 200}))["value"]]
    return sorted({(n[17:25], n[:3], track) for n in names})  # (YYYYMMDD, platform, track)


def load_track(track, direction, transform, shape, tok):
    body = {"collections": ["sentinel-1-rtc"], "datetime": f"{START}T00:00:00Z/{END}T23:59:59Z", "limit": 500,
            "intersects": {"type": "Point", "coordinates": [121.265, 14.15]}, "query": {"sat:relative_orbit": {"eq": track}, "sat:orbit_state": {"eq": direction}}}
    items = sorted(get(f"{PC}/stac/v1/search", json.dumps(body).encode())["features"], key=lambda f: f["properties"]["datetime"])
    dates = [f["properties"]["datetime"] for f in items]
    # Streamed windows are cached in /tmp (RAM-backed here); delete vv_<track>.npz to re-stream.
    cache = f"{OUT}/vv_{track}.npz"
    if os.path.exists(cache) and list(np.load(cache)["dates"]) == dates:
        stack = np.load(cache)["vv"]
    else:
        with ThreadPoolExecutor(4) as ex:
            stack = np.stack(list(ex.map(lambda f: to_db(warp(f["assets"]["vv"]["href"] + "?" + tok, transform, shape)).astype("float16"), items)))
        np.savez(cache, vv=stack, dates=np.array(dates))
    print(track, direction, len(dates), "RTC scenes", dates[0][:10], "->", dates[-1][:10], flush=True)
    return dates, [f["properties"]["platform"].upper() for f in items], stack


def main(only):
    os.makedirs(OUT, exist_ok=True)
    transform, shape = grid()
    tok = get(f"{PC}/sas/v1/token/sentinel-1-rtc")["token"]
    # Smooth the 30 m surface model first: raw, its tree and roof edges read as steep slopes across flat paddies.
    dem = gaussian_filter(np.nan_to_num(warp(DEM, transform, shape)), DEM_SMOOTH_PX)
    gy, gx = np.gradient(dem, PX * 0.97)  # mercator to ground scale at 14.1 N
    steep = np.degrees(np.arctan(np.hypot(gx, gy))) >= MAX_SLOPE_DEG
    lc = warp(WC, transform, shape, Resampling.nearest, "uint8")
    low_conf = np.isin(lc, (40, 90, 95))  # cropland, herbaceous wetland, mangroves
    blind = np.isin(lc, (10, 50))  # tree cover, built-up

    rows = []  # (utc, platform, track, class array, loose flood, strict flood, threshold)
    dry_ref = []
    tracks = {t: d for t, d in TRACKS.items() if not only or t in only}
    for track, direction in tracks.items():
        dates, platforms, stack = load_track(track, direction, transform, shape, tok)
        hist = np.load(f"{OUT}/history_{track}.npz")
        thr = [otsu(s.astype("float32")) for s in stack]
        dry = [i for i, d in enumerate(dates) if d[5:7] in ("02", "03", "04")]
        dry_ref += [dates[i] for i in dry]
        permanent = np.mean(np.stack([stack[i].astype("float32") < thr[i] for i in dry]), 0) >= PERMANENT_SHARE
        ref = np.nanmedian(np.stack([stack[i].astype("float32") for i in dry]), 0)
        lab, _ = label(permanent)
        lake = lab == np.bincount(lab[lab > 0]).argmax()  # Laguna de Bay: the largest permanent water body

        def flood(s, z, t, shift, zthr, drop):
            # Hybrid: water connected to the lake is inundation even when it returns every wet season, so it only has
            # to be darker than the dry season. Isolated water, mostly paddies, must also be unusual for its month.
            seasonal = z <= zthr
            cand = (s < t + shift) & ~permanent & ~steep & (seasonal | (s - ref <= -drop))
            lab, _ = label(cand | lake)
            linked = cand & np.isin(lab, np.unique(lab[lake]))
            f = linked | (cand & seasonal)
            return f, f & low_conf & ~linked  # isolated cropland or wetland water stays low confidence

        for i, d in enumerate(dates):
            s = stack[i].astype("float32")
            m = int(d[5:7]) - 1
            z = (s - hist["median"][m].astype("float32")) / hist["sigma"][m].astype("float32")
            f, low = flood(s, z, thr[i], 0.0, Z_THR, DROP_DB)
            c = np.full(shape, DRY, "uint8")
            c[f] = FLOOD
            c[low] = FLOOD_LOW
            c[blind & ~f] = BLIND
            c[permanent] = PERMANENT
            c[~np.isfinite(s) | ~np.isfinite(z) | (steep & ~permanent)] = NODATA
            variants = [np.packbits(v[0] & ~v[1]) for v in (flood(s, z, thr[i], *LOOSE), flood(s, z, thr[i], *STRICT))]
            rows.append((d, platforms[i], track, c, *variants, thr[i]))
        del stack
    rows.sort(key=lambda r: r[0])
    np.savez_compressed(f"{OUT}/classes.npz", classes=np.stack([r[3] for r in rows]), loose=np.stack([r[4] for r in rows]), strict=np.stack([r[5] for r in rows]),
                        dates=np.array([r[0] for r in rows]), platforms=np.array([r[1] for r in rows]), tracks=np.array([r[2] for r in rows]),
                        thresholds=np.array([r[6] for r in rows]), transform=np.array(transform)[:6], dry_season=np.array(sorted(dry_ref)),
                        acquired=np.array([f"{d}:{p}:{t}" for t in tracks for d, p, _ in acquisitions(t)]))
    print(len(rows), "passes classified;", len(dry_ref), "dry-season reference passes")


if __name__ == "__main__":
    main({int(a) for a in sys.argv[1:]})  # optional track numbers; default all
