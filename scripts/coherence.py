"""InSAR coherence for every consecutive pair of Sentinel-1 track 32 passes over Bay, from ASF HyP3.

Coherence says whether the radar echo kept its phase between two passes. Buildings normally keep it; when water
stands between them the echo changes and coherence drops, which is how built-up flooding is mapped where backscatter
alone fails. Jobs are INSAR_ISCE_MULTI_BURST (4 bursts, 10x2 looks, about 40 m), submitted under the name below;
each product zip is read remotely and only its coherence layer is pulled.
Needs a NASA Earthdata token in .edl_token (git-ignored).
Run after floods.py: .venv/bin/python scripts/coherence.py [--submit]
Output: /tmp/mata-floods/coherence.npz (coherence 0-1 on the flood grid, reference and secondary times)
"""
import json, os, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np, rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, Resampling

GRID, OUT = "/tmp/mata-floods/classes.npz", "/tmp/mata-floods/coherence.npz"
HYP3, CMR = "https://hyp3-api.asf.alaska.edu", "https://cmr.earthdata.nasa.gov/search/granules.json?"
BURSTS = ["067578_IW1", "067578_IW2", "067579_IW1", "067579_IW2"]  # track 32 bursts covering every Bay barangay
NAME, BBOX = "mata-bay-d32", "121.2055,14.0823,121.3013,14.1981"
AUTH = {"Authorization": f"Bearer {open('.edl_token').read().strip()}", "Content-Type": "application/json"}
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"


def call(url, body=None):
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None, AUTH)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def submit():
    by = {}
    q = {"collection_concept_id": "C2709161906-ASF", "bounding_box": BBOX, "temporal": "2024-11-15T00:00:00Z,2026-11-15T23:59:59Z", "page_size": 2000}
    for e in call(CMR + urllib.parse.urlencode(q))["feed"]["entry"]:
        t = e["title"]  # S1_<burst>_<swath>_<date>T<time>_VV_<id>-BURST
        if "_VV_" in t and t[3:13] in BURSTS:
            by.setdefault(t[14:22], {})[t[3:13]] = t
    dates = sorted(d for d, b in by.items() if len(b) == len(BURSTS))
    jobs = [{"job_type": "INSAR_ISCE_MULTI_BURST", "name": NAME, "job_parameters": {"reference": [by[a][k] for k in BURSTS], "secondary": [by[b][k] for k in BURSTS], "looks": "10x2"}}
            for a, b in zip(dates, dates[1:])]
    print(len(call(f"{HYP3}/jobs", {"jobs": jobs})["jobs"]), "jobs submitted for", len(dates), "dates")


def main():
    jobs = [j for j in call(f"{HYP3}/jobs?name={NAME}")["jobs"] if j["status_code"] == "SUCCEEDED"]
    z = np.load(GRID)
    T, shape = Affine(*z["transform"]), z["classes"].shape[1:]

    def load(j):
        f = j["files"][0]
        member = f["filename"].removesuffix(".zip") + "/" + f["filename"].removesuffix(".zip") + "_corr.tif"
        dst = np.full(shape, np.nan, "float32")
        with rasterio.open(f"/vsizip//vsicurl/{f['url']}/{member}") as src:
            reproject(rasterio.band(src, 1), dst, dst_transform=T, dst_crs="EPSG:3857", resampling=Resampling.bilinear, src_nodata=0, dst_nodata=np.nan)
        params = j["job_parameters"]
        return dst.astype("float16"), params["reference"][0][14:29], params["secondary"][0][14:29]

    with ThreadPoolExecutor(6) as ex:
        res = sorted(ex.map(load, jobs), key=lambda r: r[1])
    np.savez_compressed(OUT, coh=np.stack([r[0] for r in res]), reference=np.array([r[1] for r in res]), secondary=np.array([r[2] for r in res]))
    print(len(res), "coherence pairs", res[0][1], "->", res[-1][2])


if __name__ == "__main__":
    submit() if "--submit" in sys.argv else main()
