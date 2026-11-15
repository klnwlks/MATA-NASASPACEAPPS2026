"""Classify every Sentinel-1 acquisition over Laguna province on both tracks into dry / water / flood, per 10 m pixel.

Inputs (streamed as row blocks, nothing large lands on disk except the caches below):
  - Planetary Computer `sentinel-1-rtc` (gamma0, terrain corrected with GLO-30), VV only, 2024-11-15 to 2026-11-15, descending
    track 32 and ascending track 142. Adjacent scene slices are mosaicked for each track and date.
  - A per-pixel dry-season median from February–April passes in the same replay window and track.
  - Copernicus Data Space catalogue: the list of acquisitions, so dates acquired but absent from the RTC collection are
    recorded as missing (`acquired` in grid.npz) rather than silently dropped.
  - Copernicus GLO-30 (slope mask; four 1-degree tiles N13/N14 x E120/E121, each warped and fmax-combined) and ESA WorldCover
    2021 tile N12E120 (cropland and wetland low confidence unless lake-connected; tree cover and built-up radar-blind).
Method: water is below the per-pass Otsu threshold. A flood candidate is water outside permanent water, at least 3 dB
darker than the dry-season median and on slopes under 5 degrees. Isolated cropland or wetland water is low confidence.
The classification is repeated with looser and stricter thresholds for hectare ranges. The four-year seasonal baseline
is deferred, so seasonal agricultural changes may be misclassified as flood. This implementation is specific to Laguna;
its permanent-water connectivity must not be reused as a generic river connectivity model for other provinces.

Phase A, per track: stream every Feb-Apr pass of the window, per-pass Otsu threshold, running count for `permanent` (at least
80 % of the dry passes below their threshold), `ref` = per-pixel median over the dry passes, lake = largest permanent
component. Written as soon as a track finishes: CACHE/ref_<track>.npy (float16 dB) and the keys permanent_<track>,
lake_<track>, lake (union of the lakes so far) in grid.npz. Resumable per dry pass (CACHE/dry_<track>/, deleted when done).
Phase B, every pass in time order (both tracks interleaved, scenes prefetched in a thread pool): the dry-season change rule
for base / LOOSE / STRICT, the class raster to CACHE/cls/<YYYYMMDD>_<track>.npz, and per-barangay
numbers accumulated into CACHE/stats.npz. A pass whose cls file exists is skipped (its numbers are re-read from that file).

Files written (CACHE = common.CACHE, atomically via rename):
  grid.npz   transform (6), shape, psgc (barangay order), dates (UTC iso, all RTC passes), platforms, tracks, thresholds (nan until
             classified), dry_season (UTC iso of the Feb-Apr passes), acquired ("YYYYMMDD:platform:track"), then per track
             permanent_<track> and lake_<track>, and lake: np.packbits of the flattened (H, W) bool raster.
  cls/<YYYYMMDD>_<track>.npz   c: uint8 (H, W) class raster (see common.py); also this pass's rows high, low, visible, strict,
             loose (n_barangays + 1, column 0 = outside any barangay), thr, utc, platform.
  stats.npz  high, low, strict, loose (hectares: FLOOD pixels / FLOOD_LOW pixels / flood minus low confidence under the strict and
             loose rules), visible (share of the barangay's pixels that are neither NODATA nor BLIND), each (passes, n_barangays + 1);
             dates (UTC iso), platforms, tracks, thresholds. Passes are sorted by UTC time.
  S1CORE_STATUS.txt  progress and ETA.
Run: .venv/bin/python scripts/floods.py [track ...]. No historical normalization is required.
"""
import json, os, shutil, sys, threading, time, urllib.parse, urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import numpy as np, rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import Window, from_bounds
from scipy.ndimage import gaussian_filter, label, uniform_filter

from common import CACHE, PROVINCE, START, END, TRACKS, PX, NODATA, DRY, PERMANENT, FLOOD, FLOOD_LOW, BLIND, barangay_raster, features, grid, px_ha

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("GDAL_CACHEMAX", "200")  # MB, shared by all reader threads (default is 5 % of RAM)
PC = "https://planetarycomputer.microsoft.com/api"
CDSE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?"
DEM_TILES = [f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{la}_00_E{lo}_00_DEM/Copernicus_DSM_COG_10_N{la}_00_E{lo}_00_DEM.tif"
             for la in (13, 14) for lo in (120, 121)]
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif"
Z_THR, DROP_DB, MAX_SLOPE_DEG, PERMANENT_SHARE = -2.0, 3.0, 5.0, 0.8
# Sensitivity for hectare ranges: (water threshold shift dB, z threshold, dry-season drop dB) for loose and strict.
BASE, LOOSE, STRICT = (0.0, Z_THR, DROP_DB), (1.0, -1.5, 2.0), (-1.0, -2.5, 4.0)
DEM_SMOOTH_PX = 6  # about 60 m, as in terrain.py
ACQUIRED_POINT = (121.32, 14.28)  # province centre, for the CDSE catalogue
# History is stored as uint8: median at Q_STEP dB from Q_MIN (255 = no data), sigma at SIG_STEP dB (clip 12.7 dB, 255 = no data).
Q_MIN, Q_STEP, Q_NONE, SIG_STEP = -40.0, 0.2, 255, 0.05
ROWS, PAD = 500, 3  # row block of a streamed scene, and the pad of the 5 x 5 boxcar
CHUNK = 256  # rows per working chunk in the per-pass arithmetic
PREFETCH = int(os.environ.get("S1_PREFETCH", 3))  # scenes in flight or waiting, each about 100 MB as float16


def get(url, data=None, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))


class Sas:
    """Planetary Computer SAS token, refreshed 15 minutes before it expires, shared by all threads."""
    def __init__(self):
        self.lock, self.token, self.until = threading.Lock(), None, 0.0

    def __call__(self):
        with self.lock:
            if time.time() >= self.until:
                r = get(f"{PC}/sas/v1/token/sentinel-1-rtc")
                self.token = r["token"]
                exp = r.get("msft:expiry")
                self.until = (datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp() if exp else time.time() + 3000) - 900
            return self.token


def province_bbox(T, shape):
    return transform_bounds("EPSG:3857", "EPSG:4326", T.c, T.f - shape[0] * PX, T.c + shape[1] * PX, T.f)


def rtc_items(track, direction, start, end, bbox):
    """Group adjacent RTC slices from the same track and date into one observation."""
    body = {"collections": ["sentinel-1-rtc"], "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 1000, "bbox": list(bbox),
            "query": {"sat:relative_orbit": {"eq": track}, "sat:orbit_state": {"eq": direction}}}
    items = sorted(get(f"{PC}/stac/v1/search", json.dumps(body).encode())["features"], key=lambda f: f["properties"]["datetime"])
    groups = []
    for item in items:
        day = item["properties"]["datetime"][:10]
        if not groups or groups[-1]["properties"]["datetime"][:10] != day:
            groups.append({**item, "slices": [item]})
        else:
            groups[-1]["slices"].append(item)
    return groups


def _warp(src, Tb, shape, resampling=Resampling.bilinear, dtype="float32"):
    """Warp the part of an open raster covering (Tb, shape) in EPSG:3857 onto that window."""
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
