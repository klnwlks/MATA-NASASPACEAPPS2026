"""Second opinions per barangay and pass, added to the per-municipality manifests written by flood_summary.py.

Sources, each judged against its own dry-season noise so no source borrows another's thresholds:
  opera      NASA OPERA DSWx-S1 from the same pass: open water and inundated vegetation (opera.py -> CACHE/ev/opera.npz)
  coherence  ASF HyP3 InSAR coherence of the pair ending at this pass (track 32), over built-up pixels only (coherence.py)
  nisar      NISAR L-band HV over built-up and vegetated land, nearest acquisition within NISAR_DAYS (nisar.py)
A missing input file leaves that source out; a pass with no matching acquisition, or where a source saw under half of a
barangay, is null, never 0. Same rules as the Bay run (2 ha floor, 3x noise, 6-day NISAR window, coherence baseline per gap
class, built-up masks, 2 km inland control); the only plumbing differences are that dry-season noise is taken per track (two
viewing geometries never share a noise level) and that the coherence rule is applied on the coarse coherence grid with
nearest upsampling to the 10 m built-up mask (exact, through a per-cell table of built pixels per barangay).
Coherence loss and NISAR darkening are also drawn as per-municipality overlays <munipsgc>/coherence/<YYYYMMDD>.png (amber)
and <munipsgc>/nisar/<YYYYMMDD>.png (cyan), written only where non-empty; frames then carry coherenceFile / nisarFile.
Run after flood_summary.py and opera.py / nisar.py / coherence.py, then combine.py:
  .venv/bin/python scripts/evidence.py     (every source whose CACHE/ev file exists; the others are left out)
"""
import json, os, shutil, warnings
from datetime import datetime, timezone
import numpy as np
from PIL import Image
from rasterio.transform import Affine
from scipy.ndimage import distance_transform_edt

from common import CACHE, FLOODS, features, muni_crops, muni_mask, px_ha
from flood_summary import FLOOR_HA, NOISE_FACTOR, load_ids

EV = f"{CACHE}/ev"
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif"
OPERA_SEEN = 0.5
NISAR_DAYS, NISAR_SEEN, INLAND_M = 6, 0.5, 2000
COH_DROP, BUILT, MIN_REF, COH_SEEN = -0.2, 50, 3, 0.5  # coherence lost against same-baseline dry-season median; WorldCover built-up; reference pairs needed
AMBER, CYAN = (183, 121, 31, 200), (14, 157, 184, 200)  # design status amber; flood cyan
LAKE_STEP = 8  # the 2 km lake distance is measured on a grid this many times coarser: well under the threshold's precision


def t(s):
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def overlay(path, mask, rgba):
    """Palette PNG, index 1 where mask: transparent elsewhere. The viewer smooths its edges and keeps its colour."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.fromarray(mask.astype("uint8"), "P")
    img.putpalette([0, 0, 0, 0, *rgba], "RGBA")
    img.save(path, compress_level=9)


def flagged(values, frames, dry_months=("02", "03", "04")):
    """1 where a per-pass value clears max(floor, 3x the 95th percentile on dry-season passes of its own track); None stays None."""
    out = [None] * len(values)
    for tr in {f["track"] for f in frames}:
        idx = [i for i, f in enumerate(frames) if f["track"] == tr]
        dry = [values[i] for i in idx if values[i] is not None and frames[i]["utc"][5:7] in dry_months]
        if not dry:
            continue
        limit = max(FLOOR_HA, NOISE_FACTOR * float(np.percentile(dry, 95)))
        for i in idx:
            out[i] = None if values[i] is None else int(values[i] >= limit)
    return out


class Ctx:
    """Everything the three sources share: frames, grid, barangay ids and the places evidence is written to."""

    def __init__(self):
        self.index = json.load(open(f"{FLOODS}/index.json"))
        self.frames = self.index["frames"]
        g = np.load(f"{CACHE}/grid.npz")
        self.T, self.shape = Affine(*g["transform"]), tuple(int(x) for x in g["shape"])
        self.feats = features()
        self.ids = load_ids(self.T, self.shape)
        self.pxh = px_ha(self.T)
        self.area = np.bincount(self.ids.ravel(), minlength=len(self.feats) + 1) * self.pxh
        self.munis = {m: json.load(open(f"{FLOODS}/{info['manifest']}")) for m, info in self.index["municipalities"].items()}
        self.crops = muni_crops(self.ids, self.feats)
        self.rec = {i + 1: self.munis[f["properties"]["munipsgc"]]["barangays"][f["properties"]["psgc"]] for i, f in enumerate(self.feats)}
        self.g = g
        self.lake = None

    def mask(self, m):
        return muni_mask(self.ids, self.feats, m, self.crops[m])

    def inland8(self):
        """Boolean raster on the LAKE_STEP-coarse grid: more than INLAND_M from Laguna de Bay (the province's largest permanent water)."""
        if self.lake is None:
            h, w = self.shape
            lake = np.unpackbits(self.g["lake"])[: h * w].reshape(h, w)
            hc, wc = -(-h // LAKE_STEP), -(-w // LAKE_STEP)
            pad = np.zeros((hc * LAKE_STEP, wc * LAKE_STEP), bool)
            pad[:h, :w] = lake
            near = pad.reshape(hc, LAKE_STEP, wc, LAKE_STEP).any((1, 3))
            self.lake = distance_transform_edt(~near) * LAKE_STEP * (self.pxh * 1e4) ** 0.5 > INLAND_M
        return self.lake

    def set_evidence(self, name, label, flags, details, method):
        """flags/details: {barangay raster id: list over frames}."""
        for b, fl in flags.items():
            self.rec[b].setdefault("evidence", {})[name] = {"label": label, "flagged": fl, "detail": details[b]}
        self.index["method"][name] = method

    def set_file(self, m, fi, key, rel):
        self.munis[m]["frames"][fi][key] = rel


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
