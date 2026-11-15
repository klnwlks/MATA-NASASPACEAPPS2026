"""InSAR coherence for every consecutive pair of Sentinel-1 track 32 passes over Laguna province, from ASF HyP3.

Coherence says whether the radar echo kept its phase between two passes. Buildings normally keep it; when water
stands between them the echo changes and coherence drops, which is how built-up flooding is mapped where backscatter
alone fails. Jobs are INSAR_ISCE_MULTI_BURST (10x2 looks, about 40 m), one job per pair covering all bursts below.
Needs a NASA Earthdata token in .edl_token (git-ignored). Same method as the Bay run; only the burst set, the grid and
the storage scale changed.

Usage (cwd = repo root, resumable and idempotent; HyP3 jobs take hours, so run each step as often as you like):
  .venv/bin/python scripts/coherence.py --status    job counts by status, burst plan, expected credits (no spend)
  .venv/bin/python scripts/coherence.py --test      submit ONE pair under TEST_NAME (the first pair) and nothing else
  .venv/bin/python scripts/coherence.py --submit    submit every pair that has no job yet (under NAME; the test pair is
                                                    reused, never paid twice); refuses to spend more than BUDGET credits
  .venv/bin/python scripts/coherence.py             fetch every SUCCEEDED job not yet on disk, then rewrite the index

Bursts: those of track 32 whose CMR footprint covers at least BURST_MIN_SHARE of Laguna's land (union of the barangays),
checked to cover every barangay completely. On 2024-11-19 that is 067576..067579 x IW1, IW2 (8 bursts; 10 credits is the
HyP3 price for 10 to 15 bursts, 5 credits for 4 to 9 at 10x2, from GET /costs). Only dates on which every one of those
bursts exists in VV are paired, as in Bay; a missing burst drops the date, the neighbours then pair across it (longer gap).
A job takes at most 15 bursts, so one job per pair suffices and no mosaicking of jobs is needed.

Coarse grid (the products are about 40 m native, so full 10 m grids would only be interpolation):
  factor 4, pixel 4*PX m, transform = common.grid() transform * Affine.scale(4), shape = ceil(H/4), ceil(W/4), EPSG:3857.
  Each pair's _corr.tif (the only zip member read, remotely via /vsizip) is bilinearly reprojected onto it.
  evidence.py applies its dry-season median and drop rule on this grid and upsamples with nearest neighbour to the 10 m
  built-up mask (coarse pixel (r, c) covers fine rows 4r..4r+3, columns 4c..4c+3).

Output, all under CACHE/ev/ (about 3 Mpx float16 = 6 MB per pair uncompressed, 50-90 pairs):
  coh/<refYYYYMMDD>_<secYYYYMMDD>.npy   float16 (h, w) coherence 0-1 on the coarse grid, NaN where the product has no
                                        data (outside the swath, or zero coherence = no signal); never zero-filled
  coherence.npz                         the index evidence.py reads:
      reference, secondary   str (n,)   'YYYYMMDDTHHMMSS' of the first burst, sorted by reference, same as the Bay file
      gap                    int16 (n,) days between the passes, 5-7 pooled as 6 (the same gap_class evidence.py uses)
      files                  str (n,)   file names under CACHE/ev/coh/ in the same order
      transform              float64 (6,) affine of the coarse grid (a, b, c, d, e, f), EPSG:3857
      shape                  int (2,)   coarse (h, w);  factor  int  4;  px  float  coarse pixel size in metres
      bursts                 str (k,)   the burst ids in every job
  Per-pair arrays are loaded one at a time from coh/ (np.load(CACHE/ev/coh/<file>)); never stack them all at full float32.
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import numpy as np, rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, Resampling
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(__file__))
from common import CACHE, features, grid

HYP3, CMR = "https://hyp3-api.asf.alaska.edu", "https://cmr.earthdata.nasa.gov/search/granules.json?"
NAME, TEST_NAME = "mata-laguna-d32", "mata-laguna-test"
BURST_COLLECTION, REF_DATE = "C2709161906-ASF", "2024-11-19"  # burst SLC collection; a track-32 date inside the window
BURST_MIN_SHARE, MAX_BURSTS, BUDGET = 0.01, 15, 1000
WINDOW = ("2024-11-15T00:00:00Z", "2026-11-15T23:59:59Z")
FACTOR, THREADS = 4, 3
OUT, COH = f"{CACHE}/ev/coherence.npz", f"{CACHE}/ev/coh"
AUTH = {"Authorization": f"Bearer {open('.edl_token').read().strip()}", "Content-Type": "application/json"}
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"


def call(url, body=None, headers=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, json.dumps(body).encode() if body else None, headers if headers is not None else AUTH)
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code < 500 or k == tries - 1:
                raise RuntimeError(f"{url}: {e.code} {e.read()[:400]!r}") from None
        except OSError:
            if k == tries - 1:
                raise
        import time; time.sleep(5 * (k + 1))


def cmr(**q):
    out, page = [], 1
    while True:
        r = call(CMR + urllib.parse.urlencode({"collection_concept_id": BURST_COLLECTION, "page_size": 2000, "page_num": page, **q}, doseq=True), headers={})
        out += r["feed"]["entry"]
        if len(r["feed"]["entry"]) < 2000:
            return out
        page += 1


def select_bursts():
    """Burst ids (e.g. '067578_IW1') of the reference date that cover >= BURST_MIN_SHARE of Laguna, with the proof that
    together they cover every barangay."""
    es = cmr(bounding_box="121.0,13.95,121.65,14.6", temporal=f"{REF_DATE}T00:00:00Z,{REF_DATE}T23:59:59Z")
    polys = {}
    for e in es:
        if "_VV_" in e["title"]:
            p = [float(x) for x in e["polygons"][0][0].split()]
            polys[e["title"][3:13]] = Polygon(list(zip(p[1::2], p[0::2])))
    geoms = [shape(f["geometry"]) for f in features()]
    land = unary_union(geoms)
    chosen = sorted(k for k, v in polys.items() if v.intersection(land).area / land.area >= BURST_MIN_SHARE)
    cover = unary_union([polys[k] for k in chosen])
    short = [i for i, g in enumerate(geoms) if g.difference(cover).area / g.area > 1e-6]
    assert not short, f"{len(short)} barangays not covered by bursts {chosen}"
    assert len(chosen) <= MAX_BURSTS, "burst set does not fit one HyP3 job: split into adjacent jobs and mosaic"
    return chosen


def burst_titles(bursts):
    """{date: {burst id: granule title}} for every burst over the window (VV only), one CMR query per burst."""
    by = {}
    for b in bursts:
        for e in cmr(**{"readable_granule_name[]": f"S1_{b}_*_VV_*", "options[readable_granule_name][pattern]": "true", "temporal": ",".join(WINDOW)}):
            t = e["title"]  # S1_<burst>_<swath>_<date>T<time>_VV_<id>-BURST
            by.setdefault(t[14:22], {})[t[3:13]] = t
    return by


def pairs(bursts):
    by = burst_titles(bursts)
    dates = sorted(d for d, b in by.items() if len(b) == len(bursts))
    skipped = sorted(d for d in by if d not in dates)
    return [(a, b, [by[a][k] for k in bursts], [by[b][k] for k in bursts]) for a, b in zip(dates, dates[1:])], dates, skipped


def all_jobs(name):
    jobs, url = [], f"{HYP3}/jobs?name={name}"
    while url:
        r = call(url)
        jobs += r["jobs"]
        url = r.get("next")
    return jobs


def pair_key(job):
    p = job["job_parameters"]
    return p["reference"][0][14:22], p["secondary"][0][14:22]


def credits():
    return call(f"{HYP3}/user")["remaining_credits"]


def cost(n_bursts):
    t = call(f"{HYP3}/costs")["INSAR_ISCE_MULTI_BURST"]["cost_table"]["10x2"]
    return t[str(n_bursts)]


def status():
    bursts = select_bursts()
    ps, dates, skipped = pairs(bursts)
    existing = {n: all_jobs(n) for n in (NAME, TEST_NAME)}
    have = {pair_key(j) for js in existing.values() for j in js}
    per = cost(len(bursts))
    todo = [p for p in ps if p[:2] not in have]
    print(f"bursts ({len(bursts)}): {bursts}")
    print(f"dates with every burst: {len(dates)}, dates missing a burst (not paired): {skipped}; pairs: {len(ps)}")
    for n, js in existing.items():
        print(n, len(js), dict(Counter(j["status_code"] for j in js)))
    print(f"pairs without a job: {len(todo)}; {per} credits each = {per * len(todo)}; remaining credits {credits()}")
    return bursts, ps, todo, per


def job_body(name, p):
    return {"job_type": "INSAR_ISCE_MULTI_BURST", "name": name, "job_parameters": {"reference": p[2], "secondary": p[3], "looks": "10x2"}}


def submit(test):
    bursts, ps, todo, per = status()
    if test:
        if any(pair_key(j) == ps[0][:2] for j in all_jobs(TEST_NAME)):
            return print("test job already exists")
        todo = ps[:1]
    if per * len(todo) > BUDGET:
        sys.exit(f"would spend {per * len(todo)} credits, over the {BUDGET} budget: not submitting")
    before = credits()
    name = TEST_NAME if test else NAME
    for i in range(0, len(todo), 50):
        n = len(call(f"{HYP3}/jobs", {"jobs": [job_body(name, p) for p in todo[i:i + 50]]})["jobs"])
        print(f"submitted {n} jobs as {name}")
    print(f"credits {before} -> {credits()}")


def coarse_grid():
    T, (h, w) = grid()
    return T * Affine.scale(FACTOR), (-(-h // FACTOR), -(-w // FACTOR))


def pair_file(job):
    return "%s_%s.npy" % pair_key(job)


def load(job, T, shape):
    f = job["files"][0]
    stem = f["filename"].removesuffix(".zip")
    for k in range(4):  # remote ranged reads fail now and then; a pair is small, so just retry it
        try:
            dst = np.full(shape, np.nan, "float32")
            with rasterio.open(f"/vsizip//vsicurl/{f['url']}/{stem}/{stem}_corr.tif") as src:
                reproject(rasterio.band(src, 1), dst, dst_transform=T, dst_crs="EPSG:3857", resampling=Resampling.bilinear, src_nodata=0, dst_nodata=np.nan)
            break
        except rasterio.errors.RasterioError:
            if k == 3:
                raise
            import time; time.sleep(5 * (k + 1))
    np.save(f"{COH}/{pair_file(job)}.tmp.npy", dst.astype("float16"))
    os.replace(f"{COH}/{pair_file(job)}.tmp.npy", f"{COH}/{pair_file(job)}")
    return pair_file(job)


def gap_class(ref, sec):
    days = (datetime.strptime(sec[:8], "%Y%m%d") - datetime.strptime(ref[:8], "%Y%m%d")).days
    return 6 if 5 <= days <= 7 else days


def fetch():
    os.makedirs(COH, exist_ok=True)
    T, shape = coarse_grid()
    jobs = {}
    for n in (NAME, TEST_NAME):
        for j in all_jobs(n):
            jobs.setdefault(pair_key(j), j)
    print(dict(Counter(j["status_code"] for j in jobs.values())), "jobs over both names")
    done = [j for j in jobs.values() if j["status_code"] == "SUCCEEDED"]
    todo = [j for j in done if not os.path.exists(f"{COH}/{pair_file(j)}")]
    print(f"{len(done) - len(todo)} pairs on disk, fetching {len(todo)}")
    with ThreadPoolExecutor(THREADS) as ex:
        for name in ex.map(lambda j: load(j, T, shape), todo):
            print("fetched", name, flush=True)
    rows = sorted((j["job_parameters"]["reference"][0][14:29], j["job_parameters"]["secondary"][0][14:29], pair_file(j)) for j in done)
    if not rows:
        return print("no SUCCEEDED jobs yet")
    bursts = sorted({t[3:13] for t in done[0]["job_parameters"]["reference"]})
    np.savez_compressed(OUT, reference=np.array([r[0] for r in rows]), secondary=np.array([r[1] for r in rows]),
                        gap=np.array([gap_class(r[0], r[1]) for r in rows], "int16"), files=np.array([r[2] for r in rows]),
                        transform=np.array(T[:6]), shape=np.array(shape), factor=FACTOR, px=abs(T.a), bursts=np.array(bursts))
    print(len(rows), "coherence pairs", rows[0][0], "->", rows[-1][1], "->", OUT)


if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
    elif "--test" in sys.argv:
        submit(True)
    elif "--submit" in sys.argv:
        submit(False)
    else:
        fetch()
