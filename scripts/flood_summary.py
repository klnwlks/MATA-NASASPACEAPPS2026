"""Turn the class stack from floods.py into replay frames and per-barangay flood records.

Open water: a barangay counts as flooded on a date when its high-confidence flood area is at least FLOOR_HA and at least
three times its own noise level (95th percentile of flood area on dry-season reference dates, where no flood is expected).
Low-confidence water (cropland, wetland) is reported but never counts. Combined state and duration runs across all
sources are added by evidence.py.
Run after floods.py: .venv/bin/python scripts/flood_summary.py
Output: public/data/floods/manifest.json and one transparent PNG per observed date.
"""
import glob, json, os
from datetime import datetime
import numpy as np
from PIL import Image
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform_geom

SRC, OUT = "/tmp/mata-floods/classes.npz", "public/data/floods"
FLOOR_HA, NOISE_FACTOR, MIN_VISIBLE = 2.0, 3.0, 0.25
NODATA, DRY, PERMANENT, FLOOD, FLOOD_LOW, BLIND = range(6)
# RGBA per class: unknown (no data, steep, radar-blind) is a pale grey veil, never drawn as dry; flood is cyan, apart from
# the cobalt selection; low confidence uses the same alpha channel at 170 and the viewer draws it fainter and paler.
UNKNOWN = (120, 120, 120, 70)
PALETTE = {NODATA: UNKNOWN, BLIND: UNKNOWN, DRY: (0, 0, 0, 0), PERMANENT: (0, 0, 0, 0), FLOOD: (14, 157, 184, 215), FLOOD_LOW: (14, 157, 184, 170)}


def day(iso):
    return datetime.fromisoformat(iso[:10])


def main():
    z = np.load(SRC)
    utc = lambda d: str(d)[:19] + "Z"  # whole seconds: every browser parses this ISO form
    classes, dates, T = z["classes"], [utc(d) for d in z["dates"]], Affine(*z["transform"])
    tracks = [int(t) for t in z["tracks"]]
    n, h, w = classes.shape
    unpack = lambda bits: np.unpackbits(bits)[: h * w].reshape(h, w).astype(bool)
    px_ha = (abs(T.a) * 0.97) ** 2 / 1e4  # mercator pixel to ground hectares at 14.1 N
    feats = json.load(open("public/data/barangays.geojson"))["features"]
    ids = rasterize([(transform_geom("EPSG:4326", "EPSG:3857", f["geometry"]), i + 1) for i, f in enumerate(feats)], out_shape=(h, w), transform=T, dtype="int16")
    in_muni = ids > 0
    dry_ref = {utc(d) for d in z["dry_season"]}

    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(f"{OUT}/[0-9]*.png"):  # frame names change with the track set; never leave orphans
        os.remove(old)
    lut = np.zeros((256, 4), "uint8")
    for k, rgba in PALETTE.items():
        lut[k] = rgba
    frames = []
    for i, d in enumerate(dates):
        rgba = lut[classes[i]]
        rgba[~in_muni] = 0  # frames show the municipality only; outside it nothing was assessed for this product
        name = f"{d[:10].replace('-', '')}_{tracks[i]}.png"
        Image.fromarray(rgba, "RGBA").save(f"{OUT}/{name}", optimize=True)
        gap = (day(d) - day(dates[i - 1])).days if i else None
        frames.append({"utc": d, "platform": str(z["platforms"][i]).upper(), "track": tracks[i], "file": name, "thresholdDb": round(float(z["thresholds"][i]), 2), "daysSincePrevious": gap})
    loose = [unpack(b) for b in z["loose"]]
    strict = [unpack(b) for b in z["strict"]]

    barangays = {}
    for b, f in enumerate(feats, 1):
        m = ids == b
        visible = np.array([(~np.isin(classes[i][m], (NODATA, BLIND))).mean() for i in range(n)])
        high = np.array([(classes[i][m] == FLOOD).sum() * px_ha for i in range(n)])
        low = np.array([(classes[i][m] == FLOOD_LOW).sum() * px_ha for i in range(n)])
        span = [[round(float(strict[i][m].sum() * px_ha), 1), round(float(loose[i][m].sum() * px_ha), 1)] for i in range(n)]
        # Noise per track: each viewing geometry has its own clutter, so a pass is judged against its own track's dry season.
        noise = {t: float(np.percentile([high[i] for i, d in enumerate(dates) if d in dry_ref and tracks[i] == t], 95)) for t in set(tracks)}
        limit = np.array([max(FLOOR_HA, NOISE_FACTOR * noise[t]) for t in tracks])
        state = np.where(visible < MIN_VISIBLE, -1, (high >= limit).astype(int))  # -1 unknown, 0 none seen, 1 flooded
        barangays[f["properties"]["psgc"]] = {"name": f["properties"]["name"], "areaHa": round(float(m.sum() * px_ha), 1), "noiseHa": {str(t): round(v, 2) for t, v in noise.items()},
                                              "floodHa": high.round(1).tolist(), "floodHaRange": span, "lowConfidenceHa": low.round(1).tolist(), "visibleShare": visible.round(2).tolist(),
                                              "openWaterState": state.tolist()}

    to_ll = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    corners = [list(to_ll.transform(*(T * (c, r)))) for c, r in ((0, 0), (w, 0), (w, h), (0, h))]
    processed = {f"{d[:10].replace('-', '')}:{t}" for d, t in zip(dates, tracks)}
    manifest = {
        "tracks": {"32": "Sentinel-1 descending relative orbit 32, about 05:47 Philippine time", "142": "Sentinel-1 ascending relative orbit 142, about 18:05 Philippine time"},
        "window": [dates[0][:10], dates[-1][:10]], "corners": corners, "frames": frames,
        "acquiredNotProcessed": sorted(a for a in map(str, z["acquired"]) if f"{a.split(':')[0]}:{a.split(':')[2]}" not in processed),
        "dryReference": sorted(dry_ref),
        "method": {"reference": "per-pixel, per-calendar-month median and 1.4826 x MAD of VV on the same track, 2020-11-15 to 2024-11-14 (history.py)", "water": "VV below per-pass Otsu threshold",
                   "flood": "water, not permanent water, z <= -2 against the seasonal reference, slope under 5 degrees (60 m smoothed GLO-30)",
                   "floodHaRange": "high-confidence flood hectares with the water threshold -1/+1 dB and z <= -2.5/-1.5 (strict, loose)",
                   "lowConfidence": "flood pixels in ESA WorldCover 2021 cropland or wetland that are not connected to Laguna de Bay", "radarBlind": "WorldCover built-up or tree cover without detected open water: unknown",
                   "barangayFlooded": f"flood area >= {FLOOR_HA} ha and >= {NOISE_FACTOR}x the dry-season noise of the same track", "minVisibleShare": MIN_VISIBLE},
        "barangays": barangays,
    }
    json.dump(manifest, open(f"{OUT}/manifest.json", "w"), separators=(",", ":"))
    print(len(frames), "frames;", sum(sum(s == 1 for s in b["openWaterState"]) for b in barangays.values()), "open-water flooded barangay-passes;", len(manifest["acquiredNotProcessed"]), "acquired but not processed")


if __name__ == "__main__":
    main()
