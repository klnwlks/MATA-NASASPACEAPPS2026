"""Classify every Sentinel-1 descending track 32 acquisition over Bay into dry / water / flood, per 10 m pixel.

Inputs (all streamed as small windows, nothing large lands on disk):
  - Planetary Computer `sentinel-1-rtc` (gamma0, terrain corrected with GLO-30), VV only, track 32 descending,
    2024-11-15 to 2026-11-15. S1A until 2026-06, S1C from 2025-07, S1D from 2026-04: 12-day, then mostly 6-day revisit.
  - Copernicus Data Space catalogue: the full list of acquisitions, so dates acquired but absent from the
    RTC collection are recorded as missing rather than silently dropped.
  - Copernicus GLO-30 (slope mask) and ESA WorldCover 2021 (cropland and wetland flags).
Method: change detection against a dry-season reference (per-pixel median of Feb-Apr acquisitions).
Run after boundaries.py: .venv/bin/python scripts/floods.py
Output: /tmp/mata-floods/classes.npz (uint8 class stack + grid), read by scripts/flood_summary.py.
"""
import json, os, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np, rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds
from scipy.ndimage import uniform_filter

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["GDAL_HTTP_MAX_RETRY"] = "5"
START, END, TRACK = "2024-11-15", "2026-11-15", 32
PC = "https://planetarycomputer.microsoft.com/api"
CDSE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?"
DEM = "/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N14_00_E121_00_DEM/Copernicus_DSM_COG_10_N14_00_E121_00_DEM.tif"
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif"
OUT = "/tmp/mata-floods"
BUFFER_DEG, PX = 0.01, 10.31  # Web Mercator metres per pixel, about 10 m on the ground at 14.1 N
DROP_DB, MAX_SLOPE_DEG, PERMANENT_SHARE = 3.0, 5.0, 0.8
# Classes. Low-confidence water: cropland or wetland, where paddies and ponds look like water outside any flood.
NODATA, DRY, PERMANENT, FLOOD, FLOOD_LOW = 0, 1, 2, 3, 4


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


def warp(src_path, transform, shape, resampling=Resampling.bilinear, dtype="float32"):
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


def acquisitions():
    flt = (f"Collection/Name eq 'SENTINEL-1' and OData.CSC.Intersects(area=geography'SRID=4326;POINT(121.265 14.15)') and "
           "Attributes/OData.CSC.StringAttribute/any(a:a/Name eq 'productType' and a/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S') and "
           f"Attributes/OData.CSC.IntegerAttribute/any(a:a/Name eq 'relativeOrbitNumber' and a/OData.CSC.IntegerAttribute/Value eq {TRACK}) and "
           f"ContentDate/Start gt {START}T00:00:00.000Z and ContentDate/Start lt {END}T00:00:00.000Z")
    names = [p["Name"] for p in get(CDSE + urllib.parse.urlencode({"$filter": flt, "$top": 200}))["value"]]
    return sorted({(n[17:25], n[:3]) for n in names})  # (YYYYMMDD, platform)


def main():
    os.makedirs(OUT, exist_ok=True)
    transform, shape = grid()
    body = {"collections": ["sentinel-1-rtc"], "datetime": f"{START}T00:00:00Z/{END}T23:59:59Z", "limit": 500,
            "intersects": {"type": "Point", "coordinates": [121.265, 14.15]}, "query": {"sat:relative_orbit": {"eq": TRACK}, "sat:orbit_state": {"eq": "descending"}}}
    items = sorted(get(f"{PC}/stac/v1/search", json.dumps(body).encode())["features"], key=lambda f: f["properties"]["datetime"])
    tok = get(f"{PC}/sas/v1/token/sentinel-1-rtc")["token"]

    def load(item):
        return to_db(warp(item["assets"]["vv"]["href"] + "?" + tok, transform, shape))

    with ThreadPoolExecutor(4) as ex:
        scenes = list(ex.map(load, items))
    dates = [f["properties"]["datetime"] for f in items]
    print(len(dates), "RTC scenes", dates[0][:10], "->", dates[-1][:10], "grid", shape)

    dem = warp(DEM, transform, shape)
    gy, gx = np.gradient(dem, PX * 0.97)  # mercator to ground scale at 14.1 N
    steep = np.degrees(np.arctan(np.hypot(gx, gy))) >= MAX_SLOPE_DEG
    lc = warp(WC, transform, shape, Resampling.nearest, "uint8")
    low_conf = np.isin(lc, (40, 90, 95))  # cropland, herbaceous wetland, mangroves

    thr = [otsu(s) for s in scenes]
    water = [s < t for s, t in zip(scenes, thr)]
    dry_season = [i for i, d in enumerate(dates) if d[5:7] in ("02", "03", "04")]
    ref = np.nanmedian(np.stack([scenes[i] for i in dry_season]), 0)
    permanent = np.mean(np.stack([water[i] for i in dry_season]), 0) >= PERMANENT_SHARE
    classes = np.zeros((len(dates), *shape), "uint8")
    for i, (s, wet) in enumerate(zip(scenes, water)):
        c = np.full(shape, DRY, "uint8")
        flood = wet & ~permanent & (s - ref <= -DROP_DB)
        c[flood] = FLOOD
        c[flood & low_conf] = FLOOD_LOW
        c[permanent] = PERMANENT
        c[~np.isfinite(s) | (steep & ~permanent)] = NODATA
        classes[i] = c
    np.savez_compressed(f"{OUT}/classes.npz", classes=classes, dates=np.array(dates), platforms=np.array([f["properties"]["platform"] for f in items]),
                        thresholds=np.array(thr), transform=np.array(transform)[:6], dry_season=np.array([dates[i] for i in dry_season]),
                        acquired=np.array([f"{d}:{p}" for d, p in acquisitions()]))
    print("dry-season reference scenes", len(dry_season), "thresholds dB", np.round(thr, 1).tolist())


if __name__ == "__main__":
    main()
