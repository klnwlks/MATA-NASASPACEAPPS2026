"""Independent check: NASA OPERA DSWx-S1 surface-water maps over the province, on the flood grid of common.py.

DSWx-S1 is JPL's operational water classification from the same Sentinel-1 passes (both tracks, 30 m, MGRS tiles
T51PUR, T51PTS, T51PUS, T51PTR cover Laguna). It shares the radar's blind spots but not our thresholds, so agreement and
disagreement are both informative. Needs a NASA Earthdata token in .edl_token (git-ignored). Each B01_WTR tile
(~0.2 MB) is read in memory and dropped.

Granules of one pass (sensing times within GROUP_S of the group's first granule, any tile) are reprojected into the grid
(nearest, fill 255) and mosaicked, first valid pixel wins. Passes are processed one at a time, never stacked.
Track of a pass: 142 when its UTC hour is 6-15 (ascending, ~10:05), else 32 (descending, ~21:47).

Two stages, both resumable (re-running skips finished work):
  1. fetch  - per pass the mosaic is cached as CACHE/ev/opera_raw/<YYYYMMDDTHHMMSS>.npz (uint8 "w" on the grid, the OPERA WTR
              codes untouched: 0 not water, 1 open water, 3 inundated vegetation, 255 not observed; plus utc, platform, tiles).
  2. sums   - needs CACHE/grid.npz (written by floods.py) for permanent_<track>; skipped with a message until it exists.
              Writes CACHE/ev/opera.npz.
Run: .venv/bin/python scripts/opera.py            (both stages; stage 2 only when grid.npz exists)
     .venv/bin/python scripts/opera.py --sums     (stage 2 only; rebuilds opera.npz from the cached rasters)

CACHE/ev/opera.npz schema (G passes sorted by utc; B = n_barangays + 1, index 0 = pixels outside every barangay and unused):
  utc        str[G]      sensing time of the first granule of the pass, "YYYY-MM-DDTHH:MM:SSZ"
  platform   str[G]      S1A / S1C ... (several joined by "+" if the granules disagree)
  track      int16[G]    32 or 142, by the time-of-day rule above
  tiles      str[G]      MGRS tiles that contributed, joined by "+"
  water_ha   float32[G,B] hectares of OPERA open water (code 1) in the barangay outside permanent water
  veg_ha     float32[G,B] hectares of inundated vegetation (code 3) outside permanent water
  seen       float32[G,B] share of the barangay's non-permanent pixels that OPERA observed (code != 255); 0 when it has none
  px_ha      float32     ground hectares per grid pixel (common.px_ha)
Permanent water = grid.npz permanent_<track> of the pass's own track. Unknown is never zero-filled: evidence.py must treat
seen <= 0.5 as "OPERA did not see this barangay", exactly as for Bay.
"""
import io, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import numpy as np, rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds, Resampling

import common
from common import CACHE, START, END

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json?"
RAW, OUT = f"{CACHE}/ev/opera_raw", f"{CACHE}/ev/opera.npz"
GROUP_S, WORKERS, FILL = 120, 3, 255
WATER, VEG = 1, 3
TOKEN = open(".edl_token").read().strip()


def bbox_ll(T, shape):
    w, n = T * (0, 0); e, s = T * (shape[1], shape[0])
    lon = lambda x: np.degrees(x / 6378137.0)
    lat = lambda y: np.degrees(2 * np.arctan(np.exp(y / 6378137.0)) - np.pi / 2)
    return f"{lon(w)},{lat(s)},{lon(e)},{lat(n)}"


def granules(bbox):
    out, page = [], 1
    while True:
        q = {"short_name": "OPERA_L3_DSWX-S1_V1", "bounding_box": bbox, "temporal": f"{START}T00:00:00Z,{END}T23:59:59Z", "page_size": 2000, "page_num": page}
        with urllib.request.urlopen(CMR + urllib.parse.urlencode(q), timeout=120) as r:
            e = json.loads(r.read())["feed"]["entry"]
        out += e
        if len(e) < 2000:
            return out
        page += 1


def parse(g):
    """Title: OPERA_L3_DSWx-S1_<tile>_<sensing UTC>_<production>_<platform>_30_v1.0"""
    p = g["title"].split("_")
    s = p[4]
    return {"tile": p[3], "t": datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc), "platform": p[6], "url": next(l["href"] for l in g["links"] if l["href"].startswith("https") and l["href"].endswith("_B01_WTR.tif"))}


def groups(gs):
    gs = sorted((parse(g) for g in gs), key=lambda g: g["t"])
    out = []
    for g in gs:
        if out and (g["t"] - out[-1][0]["t"]).total_seconds() <= GROUP_S:
            out[-1].append(g)
        else:
            out.append([g])
    return out


def track_of(t):
    return 142 if 6 <= t.hour < 16 else 32


def fetch(url, tries=5):
    for k in range(tries):  # PO.DAAC redirects to CloudFront; single reads occasionally stall
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"}), timeout=60) as r:
                return r.read()
        except OSError:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def mosaic(grp, T, shape):
    m = np.full(shape, FILL, "uint8")
    for g in sorted(grp, key=lambda g: g["tile"]):
        with rasterio.MemoryFile(io.BytesIO(fetch(g["url"]))) as mem, mem.open() as src:
            l, b, r, t = transform_bounds(src.crs, "EPSG:3857", *src.bounds)
            c0, c1 = max(int((l - T.c) / T.a), 0), min(int(np.ceil((r - T.c) / T.a)), shape[1])
            r0, r1 = max(int((T.f - t) / -T.e), 0), min(int(np.ceil((T.f - b) / -T.e)), shape[0])
            if c0 >= c1 or r0 >= r1:
                continue
            tmp = np.full((r1 - r0, c1 - c0), FILL, "uint8")
            reproject(rasterio.band(src, 1), tmp, dst_transform=T * Affine.translation(c0, r0), dst_crs="EPSG:3857", resampling=Resampling.nearest, src_nodata=FILL, dst_nodata=FILL)
            view = m[r0:r1, c0:c1]
            take = (view == FILL) & (tmp != FILL)
            view[take] = tmp[take]
    return m


def key(grp):
    return grp[0]["t"].strftime("%Y%m%dT%H%M%S")


def stage_fetch(grps, T, shape):
    os.makedirs(RAW, exist_ok=True)
    todo = [g for g in grps if not os.path.exists(f"{RAW}/{key(g)}.npz")]
    print(f"{len(grps)} passes, {len(todo)} to fetch", flush=True)

    def one(grp):
        m = mosaic(grp, T, shape)
        tmp = f"{RAW}/{key(grp)}.tmp.npz"
        np.savez_compressed(tmp, w=m, utc=grp[0]["t"].strftime("%Y-%m-%dT%H:%M:%SZ"), platform="+".join(sorted({g["platform"] for g in grp})), tiles="+".join(sorted({g["tile"] for g in grp})))
        os.replace(tmp, f"{RAW}/{key(grp)}.npz")
        return key(grp), (m != FILL).mean()

    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as ex:
        for i, (k, cov) in enumerate(ex.map(one, todo), 1):
            if i % 10 == 0 or i == len(todo):
                print(f"  fetched {i}/{len(todo)} (last {k}, {cov:.0%} of grid observed) {time.time() - t0:.0f} s", flush=True)


def stage_sums(grps, T, shape):
    if not os.path.exists(f"{CACHE}/grid.npz"):
        print("CACHE/grid.npz not written yet; rasters are cached, rerun with --sums after floods.py Phase A")
        return False
    z = np.load(f"{CACHE}/grid.npz")
    perm = {t: np.unpackbits(z[f"permanent_{t}"], axis=None)[: shape[0] * shape[1]].reshape(shape).astype(bool) for t in common.TRACKS}
    feats, ids = common.barangay_raster(T, shape)
    nb = len(feats) + 1
    pxh = common.px_ha(T)
    G = len(grps)
    water, veg, seen = (np.zeros((G, nb), "float32") for _ in range(3))
    utc, plat, track, tiles = [], [], [], []
    for i, grp in enumerate(grps):
        r = np.load(f"{RAW}/{key(grp)}.npz")
        w, p = r["w"], perm[track_of(grp[0]["t"])]
        sel = (ids > 0) & ~p
        total = np.bincount(ids[sel], minlength=nb)
        obs = np.bincount(ids[sel & (w != FILL)], minlength=nb)
        water[i] = np.bincount(ids[sel & (w == WATER)], minlength=nb) * pxh
        veg[i] = np.bincount(ids[sel & (w == VEG)], minlength=nb) * pxh
        seen[i] = np.divide(obs, total, out=np.zeros(nb), where=total > 0)
        utc.append(str(r["utc"])); plat.append(str(r["platform"])); tiles.append(str(r["tiles"])); track.append(track_of(grp[0]["t"]))
    np.savez_compressed(OUT, utc=np.array(utc), platform=np.array(plat), track=np.array(track, "int16"), tiles=np.array(tiles), water_ha=water, veg_ha=veg, seen=seen, px_ha=np.float32(pxh))
    print("wrote", OUT, G, "passes")
    return True


def report(grps):
    from collections import Counter
    c = Counter(g["tile"] for grp in grps for g in grp)
    print("granules per tile", dict(c), "| passes", len(grps), "| per track", dict(Counter(track_of(g[0]["t"]) for g in grps)))
    print("passes by number of tiles", dict(Counter(len({g["tile"] for g in grp}) for grp in grps)))
    if os.path.exists(f"{CACHE}/grid.npz"):
        z = np.load(f"{CACHE}/grid.npz")
        have = {(g[0]["t"].strftime("%Y-%m-%d"), track_of(g[0]["t"])) for g in grps}
        miss = [(str(d)[:10], int(t)) for d, t in zip(z["dates"], z["tracks"]) if (str(d)[:10], int(t)) not in have]
        print("S1 passes in grid.npz without any OPERA granule:", len(miss), miss)


def main():
    T, shape = common.grid()
    grps = groups(granules(bbox_ll(T, shape)))
    if "--sums" not in sys.argv:
        stage_fetch(grps, T, shape)
    report(grps)
    stage_sums(grps, T, shape)


if __name__ == "__main__":
    main()
