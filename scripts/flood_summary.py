"""Turn the class rasters and per-barangay stats from floods.py into replay frames and per-barangay flood records, per municipality.

Open water: a barangay counts as flooded on a date when its high-confidence flood area is at least FLOOR_HA and at least
three times its own noise level (95th percentile of flood area on dry-season reference dates of the same track, where no
flood is expected). Low-confidence water (cropland, wetland) is reported but never counts. A pass where fewer than
MIN_VISIBLE of the barangay was visible to the radar is unknown (-1). A track with no dry-season reference pass has no noise
level: its passes are unknown for open water (never judged against a made-up level). Combined state and duration runs
across all sources are added by evidence.py and combine.py.

Inputs (written by floods.py, see common.py): CACHE/grid.npz, CACHE/stats.npz, CACHE/cls/<YYYYMMDD>_<track>.npz (key "c").
  stats.npz: high, low, strict, loose (ha) and visible (share) of shape (passes, n_barangays + 1), column 0 = outside any
  barangay; dates, platforms, tracks, thresholds per pass. Passes are re-sorted by time here (both tracks interleaved).
Output under public/data/floods/: index.json, <munipsgc>/manifest.json (barangay records + frames[]) and one palette PNG per
municipality crop and pass, <munipsgc>/<YYYYMMDD>_<track>.png, masked to that municipality's barangays. Every frame is
written, a fully transparent one is only a few hundred bytes. The old single-municipality layout is deleted; lake.json stays.
Run after floods.py (any number of finished passes), then combine.py --primary-only:
  .venv/bin/python scripts/flood_summary.py
"""
import glob, json, os, shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform_geom

from common import CACHE, FLOODS, NODATA, DRY, PERMANENT, FLOOD, FLOOD_LOW, BLIND, crop_corners, features, muni_crops, muni_mask, px_ha

FLOOR_HA, NOISE_FACTOR, MIN_VISIBLE = 2.0, 3.0, 0.25
# RGBA per class: unknown (no data, steep, radar-blind) is a pale grey veil, never drawn as dry; flood is cyan, apart from
# the cobalt selection; low confidence uses the same alpha channel at 170 and the viewer draws it fainter and paler.
UNKNOWN = (120, 120, 120, 70)
PALETTE = {NODATA: UNKNOWN, BLIND: UNKNOWN, DRY: (0, 0, 0, 0), PERMANENT: (0, 0, 0, 0), FLOOD: (14, 157, 184, 215), FLOOD_LOW: (14, 157, 184, 170)}
METHOD = {"reference": "per-pixel median VV of February–April acquisitions on the same track within the 2024–2026 replay window",
          "water": "VV below the per-pass Otsu threshold",
          "flood": "water outside permanent water, at least 3 dB below the dry-season reference, slope under 5 degrees (60 m smoothed GLO-30)",
          "floodHaRange": "high-confidence flood hectares with water threshold -1/+1 dB and dry-season drop 4/2 dB (strict, loose)",
          "lowConfidence": "flood pixels in ESA WorldCover 2021 cropland or wetland not connected to the reference water body",
          "radarBlind": "WorldCover built-up or tree cover without detected open water: unknown",
          "barangayFlooded": f"flood area >= {FLOOR_HA} ha and >= {NOISE_FACTOR}x the dry-season noise of the same track", "minVisibleShare": MIN_VISIBLE}
TRACK_TEXT = {"32": "Sentinel-1 descending relative orbit 32, about 05:47 Philippine time", "142": "Sentinel-1 ascending relative orbit 142, about 18:05 Philippine time"}


def day(iso):
    return datetime.fromisoformat(iso[:10])


def utc(d):
    return str(d)[:19] + "Z"  # whole seconds: every browser parses this ISO form


def load_ids(T, shape):
    """int16 raster of barangay index + 1 on the grid, cached compressed next to the other CACHE products."""
    path = f"{CACHE}/ids.npz"
    if os.path.exists(path):
        z = np.load(path)
        if z["ids"].shape == tuple(shape):
            return z["ids"]
    ids = rasterize([(transform_geom("EPSG:4326", "EPSG:3857", f["geometry"]), i + 1) for i, f in enumerate(features())], out_shape=tuple(shape), transform=T, dtype="int16")
    np.savez_compressed(path, ids=ids)
    return ids


def write_png(path, idx):
    img = Image.fromarray(idx, "P")
    img.putpalette([v for k in range(6) for v in PALETTE[k]], "RGBA")
    img.save(path, compress_level=9)


def passes():
    """Frames of every processed pass in time order, with the row of that pass in stats.npz."""
    g, s = np.load(f"{CACHE}/grid.npz"), np.load(f"{CACHE}/stats.npz")
    order = sorted(range(len(s["dates"])), key=lambda i: utc(s["dates"][i]))
    return g, s, order


def main():
    g, s, order = passes()
    T, shape = Affine(*g["transform"]), tuple(int(x) for x in g["shape"])
    feats = features()
    ids = load_ids(T, shape)
    dates = [utc(s["dates"][i]) for i in order]
    tracks = [int(s["tracks"][i]) for i in order]
    n = len(order)
    pxh = px_ha(T)
    dry_ref = {utc(d) for d in g["dry_season"]}
    frames = [{"utc": d, "platform": str(s["platforms"][i]).upper(), "track": t, "id": f"{d[:10].replace('-', '')}_{t}", "thresholdDb": round(float(s["thresholds"][i]), 2),
               "daysSincePrevious": (day(d) - day(dates[k - 1])).days if k else None} for k, (i, d, t) in enumerate(zip(order, dates, tracks))]
    for f in frames:
        f["file"] = f["id"] + ".png"
    processed = {f["id"] for f in frames}
    acquired = sorted(a for a in map(str, g["acquired"]) if f"{a.split(':')[0]}:{a.split(':')[2]}" not in processed)

    # Old Bay-only layout and orphans: frames change with the pass set; lake.json is the only file kept at the top.
    for old in glob.glob(f"{FLOODS}/[0-9]*.png") + [f"{FLOODS}/manifest.json"]:
        if os.path.isfile(old):
            os.remove(old)
    for old in (f"{FLOODS}/coherence", f"{FLOODS}/nisar"):
        shutil.rmtree(old, ignore_errors=True)

    crops = muni_crops(ids, feats)
    area = np.bincount(ids.ravel(), minlength=len(feats) + 1) * pxh
    names = {f["properties"]["munipsgc"]: f["properties"]["muni"] for f in feats}
    munis = {}
    for m, crop in crops.items():
        os.makedirs(f"{FLOODS}/{m}", exist_ok=True)
        keep = {f"{fr['id']}.png" for fr in frames}
        for old in glob.glob(f"{FLOODS}/{m}/[0-9]*.png"):
            if os.path.basename(old) not in keep:
                os.remove(old)
        munis[m] = {"crop": crop, "mask": muni_mask(ids, feats, m, crop), "bgy": [i for i, f in enumerate(feats) if f["properties"]["munipsgc"] == m]}

    # Frames: one pass raster in memory at a time, cropped per municipality; zlib releases the GIL so a few threads help.
    pool = ThreadPoolExecutor(3)
    for k, (i, f) in enumerate(zip(order, frames)):
        # Existing images can have the same date and municipality but a different grid or detection method.
        # Rewrite them rather than silently reusing stale masks.
        todo = list(munis)
        c = np.load(f"{CACHE}/cls/{f['id']}.npz")["c"]
        jobs = []
        for m in todo:
            r0, r1, c0, c1 = munis[m]["crop"]
            jobs.append(pool.submit(write_png, f"{FLOODS}/{m}/{f['file']}", np.where(munis[m]["mask"], c[r0:r1, c0:c1], DRY).astype("uint8")))
        for j in jobs:
            j.result()
        if (k + 1) % 20 == 0 or k + 1 == n:
            print(f"frame {k + 1}/{n} {f['id']}", flush=True)

    high, low, vis, strict, loose = (s[x][order] for x in ("high", "low", "visible", "strict", "loose"))
    dry = np.array([d in dry_ref for d in dates])
    tr = np.array(tracks)
    noise = {t: np.percentile(high[dry & (tr == t)], 95, axis=0) for t in sorted(set(tracks)) if (dry & (tr == t)).any()}  # per barangay
    tracks_no_ref = sorted(set(tracks) - set(noise))
    index_munis, flooded = {}, 0
    for m, info in munis.items():
        barangays = {}
        for b in info["bgy"]:
            lim = np.array([max(FLOOR_HA, NOISE_FACTOR * noise[t][b + 1]) if t in noise else np.nan for t in tracks])
            state = np.where(np.isnan(lim) | (vis[:, b + 1] < MIN_VISIBLE), -1, (high[:, b + 1] >= lim).astype(int))  # -1 unknown, 0 none seen, 1 flooded
            flooded += int((state == 1).sum())
            p = feats[b]["properties"]
            barangays[p["psgc"]] = {"name": p["name"], "areaHa": round(float(area[b + 1]), 1), "noiseHa": {str(t): round(float(v[b + 1]), 2) for t, v in noise.items()},
                                    "floodHa": high[:, b + 1].round(1).tolist(), "floodHaRange": [[round(float(a), 1), round(float(c), 1)] for a, c in zip(strict[:, b + 1], loose[:, b + 1])],
                                    "lowConfidenceHa": low[:, b + 1].round(1).tolist(), "visibleShare": vis[:, b + 1].round(2).tolist(), "openWaterState": state.tolist()}
        corners = crop_corners(T, info["crop"])
        mf = [{**f, "file": f"{m}/{f['file']}"} for f in frames]
        for x in mf:
            del x["id"]
        json.dump({"name": names[m], "psgc": m, "corners": corners, "window": [dates[0][:10], dates[-1][:10]], "tracks": TRACK_TEXT, "frames": mf, "barangays": barangays},
                  open(f"{FLOODS}/{m}/manifest.json", "w"), separators=(",", ":"))
        index_munis[m] = {"name": names[m], "corners": corners, "barangays": list(barangays), "manifest": f"{m}/manifest.json"}

    index = {"window": [dates[0][:10], dates[-1][:10]], "tracks": TRACK_TEXT, "frames": frames, "dryReference": sorted(dry_ref), "acquiredNotProcessed": acquired,
             "method": dict(METHOD),
             "municipalities": index_munis}
    if tracks_no_ref:
        index["method"]["noDryReference"] = f"tracks {tracks_no_ref} have no dry-season reference pass: their open-water state is unknown"
    json.dump(index, open(f"{FLOODS}/index.json", "w"), separators=(",", ":"))
    print(n, "frames,", len(munis), "municipalities;", flooded, "open-water flooded barangay-passes;", len(acquired), "acquired but not processed")


if __name__ == "__main__":
    main()
