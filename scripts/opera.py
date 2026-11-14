"""Independent check: NASA OPERA DSWx-S1 surface-water maps over Bay, on the flood grid from floods.py.

DSWx-S1 is JPL's operational water classification from the same Sentinel-1 passes (both tracks, 30 m, MGRS tile
T51PUR). It shares the radar's blind spots but not our thresholds, so agreement and disagreement are both informative.
Needs a NASA Earthdata token in .edl_token (git-ignored). Each B01_WTR tile (~0.2 MB) is read in memory and dropped.
Run after floods.py: .venv/bin/python scripts/opera.py
Output: /tmp/mata-floods/opera.npz (uint8 class stack on the flood grid, dates, platforms, track direction)
"""
import io, json, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np, rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, Resampling

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json?"
GRID = "/tmp/mata-floods/classes.npz"
OUT = "/tmp/mata-floods/opera.npz"
START, END = "2024-11-15", "2026-11-15"
TOKEN = open(".edl_token").read().strip()


def granules(bbox):
    out, page = [], 1
    while True:
        q = {"short_name": "OPERA_L3_DSWX-S1_V1", "bounding_box": bbox, "temporal": f"{START}T00:00:00Z,{END}T23:59:59Z", "page_size": 2000, "page_num": page}
        with urllib.request.urlopen(CMR + urllib.parse.urlencode(q), timeout=120) as r:
            e = json.loads(r.read())["feed"]["entry"]
        out += e
        if len(e) < 2000:
            return sorted(out, key=lambda g: g["title"])
        page += 1


def wtr_url(g):
    return next(l["href"] for l in g["links"] if l["href"].startswith("https") and l["href"].endswith("_B01_WTR.tif"))


def main():
    z = np.load(GRID)
    T, shape = Affine(*z["transform"]), z["classes"].shape[1:]
    w, n = T * (0, 0); e, s = T * (shape[1], shape[0])
    lon = lambda x: np.degrees(x / 6378137.0)
    lat = lambda y: np.degrees(2 * np.arctan(np.exp(y / 6378137.0)) - np.pi / 2)
    gs = granules(f"{lon(w)},{lat(s)},{lon(e)},{lat(n)}")

    def fetch(url, tries=4):
        for k in range(tries):  # PO.DAAC redirects to CloudFront; single reads occasionally stall
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"}), timeout=60) as r:
                    return r.read()
            except OSError:
                if k == tries - 1:
                    raise

    def load(g):
        with rasterio.MemoryFile(io.BytesIO(fetch(wtr_url(g)))) as mem, mem.open() as src:
            dst = np.full(shape, 255, "uint8")
            reproject(rasterio.band(src, 1), dst, dst_transform=T, dst_crs="EPSG:3857", resampling=Resampling.nearest, dst_nodata=255)
            return dst

    with ThreadPoolExecutor(6) as ex:
        stack = np.stack(list(ex.map(load, gs)))
    # Title: OPERA_L3_DSWx-S1_<tile>_<sensing UTC>_<production>_<platform>_30_v1.0
    parts = [g["title"].split("_") for g in gs]
    times = [f"{p[4][:4]}-{p[4][4:6]}-{p[4][6:8]}T{p[4][9:11]}:{p[4][11:13]}:{p[4][13:15]}Z" for p in parts]
    np.savez_compressed(OUT, wtr=stack, utc=np.array(times), platform=np.array([p[6] for p in parts]))
    vals, counts = np.unique(stack, return_counts=True)
    print(len(gs), "DSWx-S1 granules", times[0], "->", times[-1], "classes", dict(zip(vals.tolist(), counts.tolist())))


if __name__ == "__main__":
    main()
