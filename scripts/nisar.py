"""NISAR L-band (HH, HV) backscatter over Bay, read as a window out of each remote GCOV HDF5 (about 1.4 GB each).

L-band reaches through canopy and between buildings better than Sentinel-1's C-band, so flooded vegetation and
lakeshore houses can show as strong HH double bounce. Coverage over Bay starts 2026-06-23, so it can test the
2026 high-lake season but none of 2025. Needs a NASA Earthdata token in .edl_token (git-ignored).
Run after floods.py: .venv/bin/python scripts/nisar.py
Output: /tmp/mata-floods/nisar.npz (HH and HV in dB on the flood grid, acquisition times, product versions)
"""
import json, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import fsspec, h5py, numpy as np
from pyproj import Transformer
from rasterio.transform import Affine, from_origin
from rasterio.warp import reproject, Resampling

GRID, OUT = "/tmp/mata-floods/classes.npz", "/tmp/mata-floods/nisar.npz"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json?"
COLLECTIONS = ("NISAR_L2_GCOV_V1", "NISAR_L2_GCOV_PROVISIONAL_V1")  # V1 wins when both exist for a time
TOKEN = open(".edl_token").read().strip()
PAD_PX = 4


def granules(bbox):
    best = {}
    for sn in COLLECTIONS:
        q = {"short_name": sn, "bounding_box": bbox, "temporal": "2024-11-15T00:00:00Z,2026-11-15T23:59:59Z", "page_size": 500}
        with urllib.request.urlopen(CMR + urllib.parse.urlencode(q), timeout=120) as r:
            for e in json.loads(r.read())["feed"]["entry"]:
                url = next(l["href"] for l in e["links"] if l["href"].startswith("https") and l["href"].endswith(".h5"))
                best.setdefault(e["time_start"][:16], (e["time_start"], url, sn))
    return sorted(best.values())


def main():
    z = np.load(GRID)
    T, shape = Affine(*z["transform"]), z["classes"].shape[1:]
    to_ll = Transformer.from_crs(3857, 4326, always_xy=True)
    (w, n), (e, s) = to_ll.transform(*(T * (0, 0))), to_ll.transform(*(T * (shape[1], shape[0])))
    fs = fsspec.filesystem("https", client_kwargs={"headers": {"Authorization": f"Bearer {TOKEN}"}})

    def load(g):
        with fs.open(g[1], "rb", block_size=4 * 2**20, cache_type="blockcache") as f, h5py.File(f, "r") as h:
            grid = h["science/LSAR/GCOV/grids/frequencyA"]
            x, y, epsg = grid["xCoordinates"][:], grid["yCoordinates"][:], int(grid["projection"][()])
            tr = Transformer.from_crs(4326, epsg, always_xy=True)
            xs, ys = zip(*(tr.transform(a, b) for a in (w, e) for b in (s, n)))
            c0, c1 = max(np.searchsorted(x, min(xs)) - PAD_PX, 0), min(np.searchsorted(x, max(xs)) + PAD_PX, len(x))
            r0, r1 = max(np.searchsorted(-y, -max(ys)) - PAD_PX, 0), min(np.searchsorted(-y, -min(ys)) + PAD_PX, len(y))
            src_t = from_origin(x[c0] - (x[1] - x[0]) / 2, y[r0] - (y[1] - y[0]) / 2, x[1] - x[0], y[0] - y[1])
            out = []
            for pol in ("HHHH", "HVHV"):
                a = grid[pol][r0:r1, c0:c1].astype("float32")
                a[~(a > 0)] = np.nan
                dst = np.full(shape, np.nan, "float32")
                reproject(10 * np.log10(a), dst, src_transform=src_t, src_crs=f"EPSG:{epsg}", dst_transform=T, dst_crs="EPSG:3857", resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
                out.append(dst.astype("float16"))
            return out

    gs = granules(f"{w},{s},{e},{n}")
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(load, gs))
    np.savez_compressed(OUT, hh=np.stack([r[0] for r in res]), hv=np.stack([r[1] for r in res]), utc=np.array([g[0] for g in gs]), version=np.array([g[2] for g in gs]))
    print(len(gs), "NISAR GCOV acquisitions", gs[0][0], "->", gs[-1][0])


if __name__ == "__main__":
    main()
