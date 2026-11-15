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


def opera(c):
    z = np.load(f"{EV}/opera.npz")
    utc = [str(u) for u in z["utc"]]
    water, veg, seen = z["water_ha"], z["veg_ha"], z["seen"]
    flags, details = {}, {}
    for b in c.rec:
        w, v = [], []
        for f in c.frames:
            k = [i for i, u in enumerate(utc) if abs((t(u) - t(f["utc"])).total_seconds()) < 120 and seen[i, b] > OPERA_SEEN]
            if k:  # same pass can come from several granules; first one that saw the barangay
                w.append(round(float(water[k[0], b]), 1)), v.append(round(float(veg[k[0], b]), 1))
            else:
                w.append(None), v.append(None)
        total = [None if x is None else x + y for x, y in zip(w, v)]
        flags[b] = flagged(total, c.frames)
        details[b] = [None if x is None else f"{x} ha water · {y} ha flooded vegetation" for x, y in zip(w, v)]
    c.set_evidence("opera", "NASA OPERA DSWx-S1", flags, details,
                   "NASA OPERA DSWx-S1 v1 (JPL), same pass; open water plus inundated vegetation, outside our permanent water; flagged at >= 2 ha and >= 3x its own dry-season noise")


def nisar(c):
    z = np.load(f"{EV}/nisar.npz")
    utc = [str(u) for u in z["utc"]]
    dark, seen, rate = z["dark_ha"], z["seen"], z["control_rate"]
    near = []  # per frame: (acquisition index, gap days) of the nearest acquisition within NISAR_DAYS
    for f in c.frames:
        cand = [(abs((t(u) - t(f["utc"])).total_seconds()), i) for i, u in enumerate(utc) if abs((t(u) - t(f["utc"])).total_seconds()) <= NISAR_DAYS * 86400]
        near.append(min(cand) if cand else None)
    flags, details = {}, {}
    for b in c.rec:
        fl, dt = [None] * len(c.frames), [None] * len(c.frames)
        for fi, n in enumerate(near):
            if n is None or seen[n[1], b] <= NISAR_SEEN:
                continue
            ha = round(float(dark[n[1], b]), 1)
            fl[fi] = int(ha >= max(FLOOR_HA, NOISE_FACTOR * float(rate[n[1]]) * c.area[b]))
            dt[fi] = f"{ha} ha darkened in HV · {utc[n[1]][:10]}, {int(n[0] // 86400)} d from pass"
        flags[b], details[b] = fl, dt
    done = {}
    for m, crop in c.crops.items():
        mask = None
        for fi, n in enumerate(near):
            if n is None:
                continue
            day = utc[n[1]][:10].replace("-", "")
            rel = f"{m}/nisar/{day}.png"
            if (m, day) not in done:
                if mask is None:
                    mask = c.mask(m)
                packed = np.load(f"{EV}/nisar_mask/{utc[n[1]][:10]}.npz")["m"]
                full = np.unpackbits(packed)[: c.shape[0] * c.shape[1]].reshape(c.shape)
                r0, r1, c0, c1 = crop
                dark_m = full[r0:r1, c0:c1].astype(bool) & mask
                done[(m, day)] = bool(dark_m.any())
                if done[(m, day)]:
                    overlay(f"{FLOODS}/{rel}", dark_m, CYAN)
            if done[(m, day)]:
                c.set_file(m, fi, "nisarFile", rel)
    c.set_evidence("nisar", "NISAR L-band", flags, details,
                   f"NISAR GCOV HV darkening >= 3 dB against low-lake acquisitions (before 2026-07-31) of the same track; flagged at >= 2 ha and >= 3x the darkening rate more than 2 km from the lake; nearest acquisition within {NISAR_DAYS} days")


SOURCES = {"opera": opera, "nisar": nisar}


def main():
    c = Ctx()
    for m, mf in c.munis.items():
        for rec in mf["barangays"].values():
            rec["evidence"] = {}
        for fr in mf["frames"]:
            fr.pop("nisarFile", None), fr.pop("coherenceFile", None)
        for d in ("nisar", "coherence"):
            shutil.rmtree(f"{FLOODS}/{m}/{d}", ignore_errors=True)
    for name, fn in SOURCES.items():
        if not os.path.exists(f"{EV}/{name}.npz"):
            print(name, "skipped: no input")
            continue
        fn(c)
        print(name, "done;", sum(sum(x or 0 for x in r["evidence"][name]["flagged"]) for r in c.rec.values() if name in r["evidence"]), "flagged barangay-passes")
    for m, info in c.index["municipalities"].items():
        json.dump(c.munis[m], open(f"{FLOODS}/{info['manifest']}", "w"), separators=(",", ":"))
    json.dump(c.index, open(f"{FLOODS}/index.json", "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
