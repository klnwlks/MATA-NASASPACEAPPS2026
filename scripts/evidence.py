"""Second opinions per barangay and pass, added to public/data/floods/manifest.json.

Sources, each judged against its own dry-season noise so no source borrows another's thresholds:
  opera      NASA OPERA DSWx-S1 from the same track-32 pass: open water and inundated vegetation (opera.py)
  coherence  ASF HyP3 InSAR coherence of the pair ending at this pass, over built-up pixels only (coherence.py)
  nisar      NISAR L-band HH over built-up and vegetated pixels, nearest acquisition within NISAR_DAYS (nisar.py)
A missing input file leaves that source out; a pass with no matching acquisition is null, never 0.
Run after flood_summary.py: .venv/bin/python scripts/evidence.py
"""
import json, os
from datetime import datetime
import numpy as np, rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform_geom, reproject, Resampling

TMP, MANIFEST = "/tmp/mata-floods", "public/data/floods/manifest.json"
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif"
FLOOR_HA, NOISE_FACTOR = 2.0, 3.0  # same rule as flood_summary.py
OPERA_WATER, OPERA_VEG, OPERA_FILL = 1, 3, 255
PERMANENT = 2
NISAR_DAYS, NISAR_LOW_LAKE_UNTIL, HV_DROP_DB, INLAND_M = 6, "2026-07-31", -3.0, 2000  # DAHITI: lake 1.1-1.2 m until late July 2026


def t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def flagged(values, dry_idx, floor=FLOOR_HA):
    """1 where a per-pass value clears max(floor, 3x its dry-season 95th percentile); None stays None."""
    dry = [values[i] for i in dry_idx if values[i] is not None]
    if not dry:
        return [None] * len(values)
    limit = max(floor, NOISE_FACTOR * float(np.percentile(dry, 95)))
    return [None if v is None else int(v >= limit) for v in values]


def opera(frames, ids, n_bgy, px_ha, permanent):
    z = np.load(f"{TMP}/opera.npz")
    wtr, utc = z["wtr"], [str(u) for u in z["utc"]]
    out = {b: {"waterHa": [], "vegHa": []} for b in range(1, n_bgy + 1)}
    for f in frames:
        same = [k for k, u in enumerate(utc) if abs((t(u) - t(f["utc"])).total_seconds()) < 120]
        m = np.full(ids.shape, OPERA_FILL, "uint8")
        for k in same:
            m = np.where((m == OPERA_FILL) & (wtr[k] != OPERA_FILL), wtr[k], m)
        for b in out:
            sel = (ids == b) & ~permanent
            seen = (m[sel] != OPERA_FILL).mean() if sel.any() else 0
            out[b]["waterHa"].append(round(float(((m == OPERA_WATER) & sel).sum() * px_ha), 1) if seen > 0.5 else None)
            out[b]["vegHa"].append(round(float(((m == OPERA_VEG) & sel).sum() * px_ha), 1) if seen > 0.5 else None)
    return out


def nisar(frames, ids, px_ha, permanent):
    """HV darkening (water replacing vegetation or soil) against the low-lake acquisitions of the same NISAR track,
    judged against the darkening rate on land more than 2 km from the lake in the same acquisition."""
    from scipy.ndimage import distance_transform_edt, label
    z = np.load(f"{TMP}/nisar.npz")
    hv, utc = z["hv"].astype("float32"), [str(u) for u in z["utc"]]
    bay = ids > 0
    lab, _ = label(permanent)
    px_m = (px_ha * 1e4) ** 0.5
    inland = bay & (distance_transform_edt(lab != np.bincount(lab[lab > 0]).argmax()) * px_m > INLAND_M)
    usable = [i for i in range(len(utc)) if np.isfinite(hv[i][bay]).mean() > 0.9]
    by_hour = {}
    for i in usable:
        by_hour.setdefault(utc[i][11:13], []).append(i)
    hits = {}  # nisar index -> {barangay: (ha, flagged)}
    for idx in by_hour.values():
        base = [i for i in idx if utc[i] < NISAR_LOW_LAKE_UNTIL]
        if len(base) < 2:
            continue  # no low-lake reference on this track: say nothing rather than guess
        ref = np.nanmean(hv[base], 0)
        for i in (i for i in idx if i not in base):
            dark = (hv[i] - ref <= HV_DROP_DB) & ~permanent
            rate = dark[inland].mean()
            hits[i] = {}
            for b in np.unique(ids[bay]):
                sel = ids == b
                ha = float(dark[sel].sum() * px_ha)
                hits[i][int(b)] = (round(ha, 1), int(ha >= max(FLOOR_HA, NOISE_FACTOR * rate * sel.sum() * px_ha)))
    out = {b: {"flagged": [None] * len(frames), "detail": [None] * len(frames)} for b in np.unique(ids[bay]).tolist()}
    for fi, f in enumerate(frames):
        near = [(abs((t(utc[i]) - t(f["utc"])).days), i) for i in hits if abs((t(utc[i]) - t(f["utc"])).total_seconds()) <= NISAR_DAYS * 86400]
        if not near:
            continue
        gap, i = min(near)
        for b, (ha, flag) in hits[i].items():
            out[b]["flagged"][fi] = flag
            out[b]["detail"][fi] = f"{ha} ha darkened in HV · {utc[i][:10]}, {gap} d from pass"
    return out


def main():
    m = json.load(open(MANIFEST))
    c = np.load(f"{TMP}/classes.npz")
    T, shape = Affine(*c["transform"]), c["classes"].shape[1:]
    permanent = c["classes"][0] == PERMANENT
    px_ha = (abs(T.a) * 0.97) ** 2 / 1e4
    feats = json.load(open("public/data/barangays.geojson"))["features"]
    ids = rasterize([(transform_geom("EPSG:4326", "EPSG:3857", f["geometry"]), i + 1) for i, f in enumerate(feats)], out_shape=shape, transform=T, dtype="int16")
    dry_idx = [i for i, f in enumerate(m["frames"]) if f["utc"][5:7] in ("02", "03", "04")]
    psgc = {i + 1: f["properties"]["psgc"] for i, f in enumerate(feats)}
    for rec in m["barangays"].values():
        rec["evidence"] = {}

    if os.path.exists(f"{TMP}/opera.npz"):
        for b, v in opera(m["frames"], ids, len(feats), px_ha, permanent).items():
            total = [None if w is None else w + g for w, g in zip(v["waterHa"], v["vegHa"])]
            detail = [None if w is None else f"{w} ha water · {g} ha flooded vegetation" for w, g in zip(v["waterHa"], v["vegHa"])]
            m["barangays"][psgc[b]]["evidence"]["opera"] = {"label": "NASA OPERA DSWx-S1", "flagged": flagged(total, dry_idx), "detail": detail}
        m["method"]["opera"] = "NASA OPERA DSWx-S1 v1 (JPL), same pass; open water plus inundated vegetation, outside our permanent water; flagged at >= 2 ha and >= 3x its own dry-season noise"

    if os.path.exists(f"{TMP}/nisar.npz"):
        for b, v in nisar(m["frames"], ids, px_ha, permanent).items():
            m["barangays"][psgc[b]]["evidence"]["nisar"] = {"label": "NISAR L-band", **v}
        m["method"]["nisar"] = f"NISAR GCOV HV darkening >= 3 dB against low-lake acquisitions (before {NISAR_LOW_LAKE_UNTIL}) of the same track; flagged at >= 2 ha and >= 3x the darkening rate more than 2 km from the lake; nearest acquisition within {NISAR_DAYS} days"

    json.dump(m, open(MANIFEST, "w"), separators=(",", ":"))
    for rec in m["barangays"].values():
        ev = rec["evidence"]
        print(rec["name"][:14].ljust(14), {k: sum(x or 0 for x in v["flagged"]) for k, v in ev.items()})


if __name__ == "__main__":
    main()
