"""Second opinions per barangay and pass, added to public/data/floods/manifest.json.

Sources, each judged against its own dry-season noise so no source borrows another's thresholds:
  opera      NASA OPERA DSWx-S1 from the same track-32 pass: open water and inundated vegetation (opera.py)
  coherence  ASF HyP3 InSAR coherence of the pair ending at this pass, over built-up pixels only (coherence.py)
  nisar      NISAR L-band HH over built-up and vegetated pixels, nearest acquisition within NISAR_DAYS (nisar.py)
A missing input file leaves that source out; a pass with no matching acquisition is null, never 0.
Coherence loss and NISAR darkening are also drawn as patterned overlays (floods/coherence/, floods/nisar/).
Run after flood_summary.py, then combine.py: .venv/bin/python scripts/evidence.py
"""
import json, os, shutil
from datetime import datetime
import numpy as np, rasterio
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform_geom, reproject, Resampling

TMP, MANIFEST, FRAMES = "/tmp/mata-floods", "public/data/floods/manifest.json", "public/data/floods"
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif"
FLOOR_HA, NOISE_FACTOR = 2.0, 3.0  # same rule as flood_summary.py
OPERA_WATER, OPERA_VEG, OPERA_FILL = 1, 3, 255
PERMANENT = 2
NISAR_DAYS, NISAR_LOW_LAKE_UNTIL, HV_DROP_DB, INLAND_M = 6, "2026-07-31", -3.0, 2000  # DAHITI: lake 1.1-1.2 m until late July 2026
COH_DROP, BUILT = -0.2, 50  # coherence lost against the dry-season median; WorldCover built-up class
AMBER, CYAN = (183, 121, 31, 200), (14, 157, 184, 200)  # design status amber; flood cyan


def overlay(name, mask, rgba):
    """Solid transparent PNG of a boolean mask on the flood grid; the viewer smooths its edges and keeps its colour."""
    img = np.zeros((*mask.shape, 4), "uint8")
    img[mask] = rgba
    os.makedirs(os.path.dirname(f"{FRAMES}/{name}"), exist_ok=True)
    Image.fromarray(img, "RGBA").save(f"{FRAMES}/{name}", optimize=True)
    return name


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
    z = np.load(f"{TMP}/nisar.npz")
    hv, utc = z["hv"].astype("float32"), [str(u) for u in z["utc"]]
    bay = ids > 0
    inland = inland_mask(ids, permanent, px_ha)
    usable = [i for i in range(len(utc)) if np.isfinite(hv[i][bay]).mean() > 0.9]
    by_hour = {}
    for i in usable:
        by_hour.setdefault(utc[i][11:13], []).append(i)
    hits, masks = {}, {}  # nisar index -> {barangay: (ha, flagged)}, nisar index -> darkened pixels in Bay
    for idx in by_hour.values():
        base = [i for i in idx if utc[i] < NISAR_LOW_LAKE_UNTIL]
        if len(base) < 2:
            continue  # no low-lake reference on this track: say nothing rather than guess
        ref = np.nanmean(hv[base], 0)
        for i in (i for i in idx if i not in base):
            dark = (hv[i] - ref <= HV_DROP_DB) & ~permanent
            rate = dark[inland].mean()
            hits[i], masks[i] = {}, dark & bay
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
        f["nisarFile"] = overlay(f"nisar/{utc[i][:10]}.png", masks[i], CYAN)
        for b, (ha, flag) in hits[i].items():
            out[b]["flagged"][fi] = flag
            out[b]["detail"][fi] = f"{ha} ha darkened in HV · {utc[i][:10]}, {gap} d from pass"
    return out


def coherence(frames, ids, px_ha, permanent, built):
    """Built-up pixels whose coherence fell COH_DROP below their dry-season median, judged against the same loss
    on built-up land more than 2 km from the lake in the same pair (rain and season move both alike)."""
    z = np.load(f"{TMP}/coherence.npz")
    coh, ref, sec = z["coh"].astype("float32"), [str(r) for r in z["reference"]], [str(s) for s in z["secondary"]]
    dry = [i for i in range(len(ref)) if ref[i][4:6] in ("02", "03", "04") and sec[i][4:6] in ("02", "03", "04")]
    base = np.nanmedian(coh[dry], 0)
    control = inland_mask(ids, permanent, px_ha) & built
    by_date = {s[:8]: i for i, s in enumerate(sec)}
    out = {b: {"flagged": [None] * len(frames), "detail": [None] * len(frames)} for b in np.unique(ids[ids > 0]).tolist()}
    for fi, f in enumerate(frames):
        i = by_date.get(f["utc"][:10].replace("-", ""))
        if i is None:
            continue
        lost = (coh[i] - base <= COH_DROP) & built
        rate = lost[control].mean()
        f["coherenceFile"] = overlay(f"coherence/{f['utc'][:10]}.png", lost & (ids > 0), AMBER)
        for b in out:
            sel = (ids == b) & built
            ha = float(lost[sel].sum() * px_ha)
            out[b]["flagged"][fi] = int(ha >= max(FLOOR_HA, NOISE_FACTOR * rate * sel.sum() * px_ha)) if sel.any() else None
            out[b]["detail"][fi] = f"{ha:.1f} of {sel.sum() * px_ha:.0f} ha built-up lost coherence · pair from {ref[i][:4]}-{ref[i][4:6]}-{ref[i][6:8]}"
    return out


def inland_mask(ids, permanent, px_ha):
    from scipy.ndimage import distance_transform_edt, label
    lab, _ = label(permanent)
    return (ids > 0) & (distance_transform_edt(lab != np.bincount(lab[lab > 0]).argmax()) * (px_ha * 1e4) ** 0.5 > INLAND_M)


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
    for f in m["frames"]:
        f.pop("nisarFile", None), f.pop("coherenceFile", None)
    for d in ("nisar", "coherence"):
        shutil.rmtree(f"{FRAMES}/{d}", ignore_errors=True)

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

    if os.path.exists(f"{TMP}/coherence.npz"):
        lc = np.zeros(shape, "uint8")
        with rasterio.open(WC) as src:
            reproject(rasterio.band(src, 1), lc, dst_transform=T, dst_crs="EPSG:3857", resampling=Resampling.nearest)
        for b, v in coherence(m["frames"], ids, px_ha, permanent, lc == BUILT).items():
            m["barangays"][psgc[b]]["evidence"]["coherence"] = {"label": "InSAR coherence, built-up", **v}
        m["method"]["coherence"] = f"ASF HyP3 INSAR_ISCE_MULTI_BURST, consecutive track-32 pairs ending at the pass; built-up pixels {COH_DROP} or more below their dry-season median coherence; flagged at >= 2 ha and >= 3x the same loss on built-up land 2 km inland"

    json.dump(m, open(MANIFEST, "w"), separators=(",", ":"))
    for rec in m["barangays"].values():
        ev = rec["evidence"]
        print(rec["name"][:14].ljust(14), {k: sum(x or 0 for x in v["flagged"]) for k, v in ev.items()})


if __name__ == "__main__":
    main()
