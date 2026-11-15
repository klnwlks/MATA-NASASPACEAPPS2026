"""NISAR L-band HV backscatter over the province: darkening against a low-lake reference, read as windows out of the remote
GCOV HDF5 files (1.5-5 GB each; only the chunks inside the province are fetched, in parallel ranged reads).

L-band reaches through canopy better than Sentinel-1's C-band, so water replacing vegetation or soil shows as HV darkening.
Coverage of the province starts 2026-06-23. Needs a NASA Earthdata token in .edl_token (git-ignored).

Granules and acquisitions. CMR lists NISAR_L2_GCOV_V1 and NISAR_L2_GCOV_PROVISIONAL_V1 granules intersecting the grid; a granule
(track, frame, mode, start minute) exists in both collections only if reprocessed: V1 wins. Granules of one NISAR track whose
start times lie within 60 s of the group's first granule form one acquisition (one frame never covers the province: frames
008 and 009 of track 140 overlap it, as do 081 and 082 of track 032). Modes: 4005 = 10 m posting, 2005 = 20 m posting (the
province is covered by both at track 140). The acquisition mosaic takes the finest posting first and fills the rest from the
coarser granules, frame order breaking ties; the same granule set repeats every 12-day cycle so a pixel always comes from
the same granule within a track. HV only (the evidence rule uses HV; HH is not read).
NISAR track groups: 140 (ascending, ~21:30 UTC), 32 (descending, ~10:24 UTC), 39 (ascending, ~21:22 UTC). Grouping is by NISAR
track, not by hour of day (hours 21:22 and 21:30 are different tracks).

Method (same as Bay). Per track group the low-lake reference is the nanmean (dB, float16 per acquisition) of the acquisitions
sensed before LOW_LAKE_UNTIL (2026-07-31, DAHITI: lake 1.1-1.2 m); a group with fewer than 2 usable (any province pixel)
reference acquisitions has no reference and says nothing (listed in unreferenced_utc). Each later acquisition is "darkened" where
HV minus reference <= HV_DROP_DB (-3 dB), outside permanent water, inside barangays. Hold-outs of one acquisition at a time in RAM.

Stages (both resumable; re-running skips finished work):
  A  needs no grid.npz: reads granules, builds references (CACHE/ev/nisar_ref/<track>.npz float16 dB "ref"), and for every
     non-reference acquisition stores CACHE/ev/nisar_mask/<key>_raw.npz {dark, fin: packbits(H*W)} where fin = HV finite in the
     acquisition and the reference, dark = fin & drop. Progress in CACHE/ev/nisar_state.json.
     If a run is killed while a reference is being accumulated, delete CACHE/ev/nisar_ref/<track>* and rerun.
  B  needs CACHE/grid.npz (floods.py Phase A): permanent water = permanent_32 OR permanent_142 (NISAR has no S1 track; being
     permanent in either geometry excludes the pixel), lake = grid.npz lake. Inland = barangay pixels >2 km from the lake,
     distance computed on a 4x block-reduced lake mask (about +-40 m on the 2 km line; the full-resolution EDT would need ~1 GB).
     Writes CACHE/ev/nisar_mask/<key>.npz and CACHE/ev/nisar.npz.
Run: .venv/bin/python scripts/nisar.py          (A then B when grid.npz exists)
     .venv/bin/python scripts/nisar.py --sums   (B only)

CACHE/ev/nisar.npz schema (A = non-reference acquisitions, sorted by utc; B = n_barangays + 1, index 0 unused):
  utc           str[A]  acquisition start, "YYYY-MM-DDTHH:MM:SSZ" (first granule of the acquisition)
  key           str[A]  "YYYYMMDDTHHMM_<track>"; the overlay mask of the acquisition is nisar_mask/<key>.npz
  track         int16[A] NISAR relative orbit (140, 32, 39)
  version       str[A]  product collection(s) used, "V1", "PROVISIONAL_V1" or both joined by "+"
  dark_ha       float32[A,B] hectares darkened (HV drop <= -3 dB vs the reference), outside permanent water; 0 where nothing seen
  seen          float32[A,B] share of the barangay's pixels (all of them, as the id raster) with finite HV in the acquisition
                AND in the reference. evidence.py reports None, never 0, below 0.5
  control_rate  float32[A] darkened share of the finite pixels more than 2 km from the lake (the noise rate of that acquisition)
  coverage      float32[A] share of all barangay pixels of the province with finite HV in both
  px_ha         float32  ground hectares per pixel
  ref_utc       str[R], ref_track int16[R]  the acquisitions used in the references
  unreferenced_utc str[U], unreferenced_track int16[U]  later acquisitions of groups without a reference (no numbers)
Overlay mask file nisar_mask/<key>.npz: key "m" = np.packbits(mask, axis=None) of the bool (H, W) grid (row-major,
default bit order; unpack with np.unpackbits(m)[:H*W].reshape(H, W)), mask = darkened & barangay pixel & not permanent;
key "shape" = (H, W).
"""
import json, os, sys, time, urllib.parse, urllib.request, zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fsspec, h5py, numpy as np
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_bounds, Resampling

import common
from common import CACHE, START, END

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json?"
COLLECTIONS = ("NISAR_L2_GCOV_V1", "NISAR_L2_GCOV_PROVISIONAL_V1")  # V1 wins when both exist for a granule
NISAR_LOW_LAKE_UNTIL, HV_DROP_DB, INLAND_M = "2026-07-31", -3.0, 2000
GROUP_S, BAND, PAD_PX, LAKE_BLOCK = 60, 1024, 3, 4
EV, REF, MASK = f"{CACHE}/ev", f"{CACHE}/ev/nisar_ref", f"{CACHE}/ev/nisar_mask"
STATE, OUT = f"{CACHE}/ev/nisar_state.json", f"{CACHE}/ev/nisar.npz"
TOKEN = open(".edl_token").read().strip()
FS = fsspec.filesystem("https", client_kwargs={"headers": {"Authorization": f"Bearer {TOKEN}"}})


def bbox_ll(T, shape):
    w, n = T * (0, 0); e, s = T * (shape[1], shape[0])
    return transform_bounds("EPSG:3857", "EPSG:4326", w, s, e, n)


def granules(bbox):
    best = {}
    for sn in COLLECTIONS:
        page = 1
        while True:
            q = {"short_name": sn, "bounding_box": ",".join(map(str, bbox)), "temporal": f"{START}T00:00:00Z,{END}T23:59:59Z", "page_size": 500, "page_num": page}
            for k in range(5):  # CMR resets connections now and then
                try:
                    with urllib.request.urlopen(CMR + urllib.parse.urlencode(q), timeout=120) as r:
                        es = json.loads(r.read())["feed"]["entry"]
                    break
                except OSError:
                    if k == 4:
                        raise
                    time.sleep(10 * (k + 1))
            for e in es:
                # NISAR_L2_PR_GCOV_<cycle>_<track>_<A/D>_<frame>_<mode>_DHDH_<A/M>_<start>_<end>_P<proc>_<N/F>_<F/P>_J_001
                p = e["title"].split("_")
                url = next(l["href"] for l in e["links"] if l["href"].startswith("https") and l["href"].endswith(".h5"))
                g = {"title": e["title"], "track": int(p[5]), "dir": p[6], "frame": int(p[7]), "mode": int(p[8]), "t": datetime.strptime(p[11], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc), "url": url, "version": sn.replace("NISAR_L2_GCOV_", "")}
                best.setdefault((g["track"], g["frame"], g["mode"], p[11][:13]), g)  # V1 listed first, so it wins
    return sorted(best.values(), key=lambda g: (g["track"], g["t"]))


def acquisitions(gs):
    out = []
    for g in gs:
        if out and out[-1][0]["track"] == g["track"] and (g["t"] - out[-1][0]["t"]).total_seconds() <= GROUP_S:
            out[-1].append(g)
        else:
            out.append([g])
    return sorted(out, key=lambda a: a[0]["t"])


def utc(a):
    return a[0]["t"].strftime("%Y-%m-%dT%H:%M:%SZ")


def key(a):
    return f"{a[0]['t'].strftime('%Y%m%dT%H%M')}_{a[0]['track']}"


def read_granule(g, T, shape, out):
    """Fill the NaN pixels of out (float16 dB, grid shape) with this granule's HV, band by band; returns pixels filled."""
    w, n = T * (0, 0); e, s = T * (shape[1], shape[0])
    with FS.open(g["url"], "rb", block_size=2**20, cache_type="readahead") as f, h5py.File(f, "r") as h:
        gr = h["science/LSAR/GCOV/grids/frequencyA"]
        x, y, epsg = gr["xCoordinates"][:], gr["yCoordinates"][:], int(gr["projection"][()])
        d = gr["HVHV"]
        ch, shp = d.chunks, d.shape
        dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
        x0, y0 = float(x[0]) - dx / 2, float(y[0]) - dy / 2
        l, b, r, t = transform_bounds("EPSG:3857", f"EPSG:{epsg}", w, s, e, n, densify_pts=21)
        c0, c1 = max(int((l - x0) / dx) - PAD_PX, 0), min(int(np.ceil((r - x0) / dx)) + PAD_PX, shp[1])
        r0, r1 = max(int((t - y0) / dy) - PAD_PX, 0), min(int(np.ceil((b - y0) / dy)) + PAD_PX, shp[0])
        if c0 >= c1 or r0 >= r1:
            return 0
        infos = []
        for i in range(r0 // ch[0], (r1 - 1) // ch[0] + 1):
            for j in range(c0 // ch[1], (c1 - 1) // ch[1] + 1):
                si = d.id.get_chunk_info_by_coord((i * ch[0], j * ch[1]))
                if si.byte_offset is not None and si.size:
                    infos.append((i, j, si.byte_offset, si.size))
    if not infos:
        return 0
    chunks = {}
    for k in range(0, len(infos), 64):
        part = infos[k:k + 64]
        for (i, j, _, _), blob in zip(part, FS.cat_ranges([g["url"]] * len(part), [p[2] for p in part], [p[2] + p[3] for p in part])):
            chunks[(i, j)] = blob
    ci0, ci1 = min(i for i, _ in chunks), max(i for i, _ in chunks)
    cj0, cj1 = min(j for _, j in chunks), max(j for _, j in chunks)
    ra0, ra1, ca0, ca1 = ci0 * ch[0], min((ci1 + 1) * ch[0], shp[0]), cj0 * ch[1], min((cj1 + 1) * ch[1], shp[1])
    filled = 0
    for R0 in range(0, shape[0], BAND):
        R1 = min(R0 + BAND, shape[0])
        bl, bb, br, bt = transform_bounds("EPSG:3857", f"EPSG:{epsg}", w, T.f - R1 * -T.e, e, T.f - R0 * -T.e, densify_pts=21)
        sc0, sc1 = max(int((bl - x0) / dx) - PAD_PX, ca0), min(int(np.ceil((br - x0) / dx)) + PAD_PX, ca1)
        sr0, sr1 = max(int((bt - y0) / dy) - PAD_PX, ra0), min(int(np.ceil((bb - y0) / dy)) + PAD_PX, ra1)
        if sc0 >= sc1 or sr0 >= sr1:
            continue
        a = np.full((sr1 - sr0, sc1 - sc0), np.nan, "float32")
        for (i, j), blob in chunks.items():
            cr0, cc0 = i * ch[0], j * ch[1]
            ia, ib, ja, jb = max(cr0, sr0), min(cr0 + ch[0], sr1), max(cc0, sc0), min(cc0 + ch[1], sc1)
            if ia >= ib or ja >= jb:
                continue
            raw = np.frombuffer(zlib.decompress(blob), "u1").reshape(4, -1).T.copy().view("<f4").reshape(ch)  # shuffle + deflate
            a[ia - sr0:ib - sr0, ja - sc0:jb - sc0] = raw[ia - cr0:ib - cr0, ja - cc0:jb - cc0]
        a[~(a > 0)] = np.nan
        np.log10(a, out=a)
        a *= 10
        tmp = np.full((R1 - R0, shape[1]), np.nan, "float32")
        reproject(a, tmp, src_transform=Affine(dx, 0, x0 + sc0 * dx, 0, dy, y0 + sr0 * dy), src_crs=f"EPSG:{epsg}", dst_transform=T * Affine.translation(0, R0), dst_crs="EPSG:3857", resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
        view = out[R0:R1]
        take = np.isnan(view) & ~np.isnan(tmp)
        view[take] = tmp[take].astype("float16")
        filled += int(take.sum())
    return filled


def mosaic(a, T, shape):
    out = np.full(shape, np.nan, "float16")
    for g in sorted(a, key=lambda g: (-g["mode"], g["frame"])):  # 4005 (10 m) before 2005 (20 m)
        t0 = time.time()
        n = read_granule(g, T, shape, out)
        print(f"    {g['title'][14:64]} {g['version']}: {n / 1e6:.1f} Mpx filled, {time.time() - t0:.0f} s", flush=True)
    return out


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state(st):
    json.dump(st, open(STATE + ".tmp", "w"), indent=1)
    os.replace(STATE + ".tmp", STATE)


def bands(shape):
    return [(r, min(r + BAND, shape[0])) for r in range(0, shape[0], BAND)]


def add_to_ref(hv, track, shape):
    os.makedirs(REF, exist_ok=True)
    sp, cp = f"{REF}/{track}_sum.npy", f"{REF}/{track}_cnt.npy"
    mk = np.lib.format.open_memmap
    sm = mk(sp, "r+") if os.path.exists(sp) else mk(sp, "w+", "float32", shape)
    ct = mk(cp, "r+") if os.path.exists(cp) else mk(cp, "w+", "uint8", shape)
    for r0, r1 in bands(shape):
        v = hv[r0:r1].astype("float32")
        ok = np.isfinite(v)
        sm[r0:r1] += np.where(ok, v, 0)
        ct[r0:r1] += ok
    sm.flush(); ct.flush()


def finalize_ref(track, shape):
    sp, cp = f"{REF}/{track}_sum.npy", f"{REF}/{track}_cnt.npy"
    sm, ct = np.load(sp, mmap_mode="r"), np.load(cp, mmap_mode="r")
    ref = np.full(shape, np.nan, "float16")
    for r0, r1 in bands(shape):
        c = ct[r0:r1]
        ref[r0:r1] = np.where(c > 0, sm[r0:r1] / np.maximum(c, 1), np.nan).astype("float16")
    del sm, ct
    np.savez_compressed(f"{REF}/{track}.npz", ref=ref)
    os.remove(sp); os.remove(cp)


def stage_a(T, shape):
    os.makedirs(MASK, exist_ok=True)
    acqs = acquisitions(granules(bbox_ll(T, shape)))
    print("granules", Counter((g["track"], g["version"]) for a in acqs for g in a), "| acquisitions", len(acqs), flush=True)
    st = load_state()
    for track in sorted({a[0]["track"] for a in acqs}):
        mine = [a for a in acqs if a[0]["track"] == track]
        base = [a for a in mine if utc(a) < NISAR_LOW_LAKE_UNTIL]
        later = [a for a in mine if utc(a) >= NISAR_LOW_LAKE_UNTIL]
        print(f"track {track}: {len(base)} reference candidates, {len(later)} later", flush=True)
        # references first
        for a in base:
            k = key(a)
            if st.get(k, {}).get("done"):
                continue
            t0 = time.time()
            hv = mosaic(a, T, shape)
            valid = float(np.isfinite(hv).mean())
            if valid > 0 and not os.path.exists(f"{REF}/{track}.npz"):
                add_to_ref(hv, track, shape)
            st[k] = {"utc": utc(a), "track": track, "role": "ref", "valid_grid": valid, "version": "+".join(sorted({g["version"] for g in a})), "done": True}
            save_state(st)
            print(f"  ref {k}: {valid:.1%} of grid finite, {time.time() - t0:.0f} s", flush=True)
        used = [k for k, v in st.items() if v["track"] == track and v["role"] == "ref" and v["valid_grid"] > 0]
        if len(used) < 2:
            print(f"  track {track}: {len(used)} usable reference acquisition(s), no reference; later acquisitions stay silent")
            for a in later:
                st[key(a)] = {"utc": utc(a), "track": track, "role": "unreferenced", "valid_grid": 0.0, "version": "", "done": True}
            save_state(st)
            continue
        if not os.path.exists(f"{REF}/{track}.npz"):
            finalize_ref(track, shape)
        todo = [a for a in later if not st.get(key(a), {}).get("done")]
        if not todo:
            continue
        ref = np.load(f"{REF}/{track}.npz")["ref"]
        for a in todo:
            k = key(a)
            t0 = time.time()
            hv = mosaic(a, T, shape)
            dark, fin = [], []
            for r0, r1 in bands(shape):
                v, rf = hv[r0:r1].astype("float32"), ref[r0:r1].astype("float32")
                ok = np.isfinite(v) & np.isfinite(rf)
                fin.append(np.packbits(ok, axis=None)); dark.append(np.packbits(ok & (v - rf <= HV_DROP_DB), axis=None))
            np.savez_compressed(f"{MASK}/{k}_raw.npz", dark=np.concatenate(dark), fin=np.concatenate(fin))
            st[k] = {"utc": utc(a), "track": track, "role": "eval", "valid_grid": float(np.isfinite(hv).mean()), "version": "+".join(sorted({g["version"] for g in a})), "done": True}
            save_state(st)
            print(f"  eval {k}: {st[k]['valid_grid']:.1%} of grid finite, {time.time() - t0:.0f} s", flush=True)
        del ref


def unpack(bits, shape):
    return np.unpackbits(bits)[: shape[0] * shape[1]].reshape(shape).astype(bool)


def inland_mask(lake, shape, px_m):
    """Pixels more than INLAND_M from the lake, from a LAKE_BLOCK-times block-reduced lake mask."""
    from scipy.ndimage import distance_transform_edt
    H, W = shape
    h, w = -(-H // LAKE_BLOCK), -(-W // LAKE_BLOCK)
    pad = np.zeros((h * LAKE_BLOCK, w * LAKE_BLOCK), bool)
    pad[:H, :W] = lake
    small = pad.reshape(h, LAKE_BLOCK, w, LAKE_BLOCK).any((1, 3))
    far = distance_transform_edt(~small) * (px_m * LAKE_BLOCK) > INLAND_M
    return np.repeat(np.repeat(far, LAKE_BLOCK, 0), LAKE_BLOCK, 1)[:H, :W]


def stage_b(T, shape):
    if not os.path.exists(f"{CACHE}/grid.npz"):
        print("CACHE/grid.npz not written yet; stage A results are cached, rerun with --sums after floods.py Phase A")
        return
    z = np.load(f"{CACHE}/grid.npz")
    perm = unpack(z["permanent_32"], shape) | unpack(z["permanent_142"], shape)
    feats, ids = common.barangay_raster(T, shape)
    nb, pxh = len(feats) + 1, common.px_ha(T)
    inland = inland_mask(unpack(z["lake"], shape), shape, abs(T.a) * 0.97) & (ids > 0)
    total = np.bincount(ids[ids > 0], minlength=nb)
    st = load_state()
    ev = sorted((v["utc"], k) for k, v in st.items() if v["role"] == "eval")
    A = len(ev)
    dark_ha, seen = np.zeros((A, nb), "float32"), np.zeros((A, nb), "float32")
    ctrl, cov = np.zeros(A, "float32"), np.zeros(A, "float32")
    for i, (_, k) in enumerate(ev):
        r = np.load(f"{MASK}/{k}_raw.npz")
        fin = unpack(r["fin"], shape)
        dark = unpack(r["dark"], shape) & ~perm & (ids > 0)
        np.savez_compressed(f"{MASK}/{k}.npz", m=np.packbits(dark, axis=None), shape=np.array(shape))
        dark_ha[i] = np.bincount(ids[dark], minlength=nb) * pxh
        seen[i] = np.divide(np.bincount(ids[fin & (ids > 0)], minlength=nb), total, out=np.zeros(nb), where=total > 0)
        n_in = (inland & fin).sum()
        ctrl[i] = (dark & inland).sum() / n_in if n_in else np.nan
        cov[i] = (fin & (ids > 0)).sum() / (ids > 0).sum()
        print(f"  {k}: coverage {cov[i]:.1%}, dark {dark_ha[i].sum():.0f} ha, control rate {ctrl[i]:.4f}", flush=True)
    refs = sorted((v["utc"], v["track"]) for v in st.values() if v["role"] == "ref" and v["valid_grid"] > 0)
    unref = sorted((v["utc"], v["track"]) for v in st.values() if v["role"] == "unreferenced")
    np.savez_compressed(OUT, utc=np.array([u for u, _ in ev]), key=np.array([k for _, k in ev]), track=np.array([st[k]["track"] for _, k in ev], "int16"), version=np.array([st[k]["version"] for _, k in ev]),
                        dark_ha=dark_ha, seen=seen, control_rate=ctrl, coverage=cov, px_ha=np.float32(pxh),
                        ref_utc=np.array([u for u, _ in refs]), ref_track=np.array([t for _, t in refs], "int16"),
                        unreferenced_utc=np.array([u for u, _ in unref]), unreferenced_track=np.array([t for _, t in unref], "int16"))
    print("wrote", OUT, A, "acquisitions;", len(refs), "reference;", len(unref), "unreferenced")


def main():
    T, shape = common.grid()
    if "--sums" not in sys.argv:
        stage_a(T, shape)
    stage_b(T, shape)


if __name__ == "__main__":
    main()
