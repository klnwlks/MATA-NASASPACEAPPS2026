"""Shared province grid and contracts for every pipeline script. Import from scripts/ (cwd = repo root).

Grid: the four selected Laguna municipalities' barangay bounds + BUFFER_DEG, Web Mercator, PX metres per pixel.
Barangay order everywhere = selected features in public/data/barangays.geojson order; raster id = index+1, 0 = outside.

Disk layout (CACHE is on disk, not tmpfs; keep it under about 3.5 GB):
  CACHE/history_<track>_med.npy, _sig.npy   uint8 (12, H, W): per-calendar-month seasonal median / sigma (see history.py)
  CACHE/cls/<YYYYMMDD>_<track>.npz          key "c": uint8 (H, W) class raster of one pass (classes below)
  CACHE/grid.npz                            written by floods.py: transform(6), shape, permanent_<track> and lake as packbits,
                                            dates, platforms, tracks, thresholds, dry_season, acquired, psgc (barangay order)
  CACHE/stats.npz                           written by floods.py: per pass x (n_barangays + 1): high, low, visible, strict, loose (hectares / pixel share)
  CACHE/ev/<source>.npz                     written by opera.py, nisar.py, coherence.py (raw per-pass numbers; evidence.py judges them)
Public output layout (written by flood_summary.py / evidence.py / combine.py), under public/data/floods/:
  index.json                 {window, tracks, frames[{utc,platform,track,thresholdDb,daysSincePrevious,id}], dryReference, acquiredNotProcessed,
                              method, municipalities{<munipsgc>:{name,corners,barangays:[psgc...],manifest}}}
  states.json                {<psgc>: "<one char per frame: 1 flooded, 0 none seen, - unknown>"}  for the province overview
  <munipsgc>/manifest.json   per-municipality barangay records in the schema Bay's manifest.json has today (barangays{psgc:{...}}, plus frames[] with url fields)
  <munipsgc>/<YYYYMMDD>_<track>.png, <munipsgc>/coherence/<YYYYMMDD>.png, <munipsgc>/nisar/<YYYYMMDD>.png   municipality crops of the grid
"""
import json
import os
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine, from_origin
from rasterio.warp import transform_bounds, transform_geom

# The map shows all of Laguna, but this run processes only Bay and three flood-prone municipalities.
PROVINCE = None
MUNICIPALITIES = frozenset(("0403402000", "0403422000", "0403426000", "0403430000"))
BARANGAYS = "public/data/barangays.geojson"
FLOODS = "public/data/floods"
CACHE = "/home/lukas/mata-cache/laguna-four"
BUFFER_DEG, PX = 0.01, 10.31
CROP_PAD_PX = 20  # municipality crops: its barangays' pixel extent plus this margin
START, END = "2024-11-15", "2026-11-15"
TRACKS = {32: "descending", 142: "ascending"}
NODATA, DRY, PERMANENT, FLOOD, FLOOD_LOW, BLIND = range(6)


def features():
    with open(BARANGAYS) as f:
        selected = [feature for feature in json.load(f)["features"] if feature["properties"]["munipsgc"] in MUNICIPALITIES]
    if {feature["properties"]["munipsgc"] for feature in selected} != MUNICIPALITIES:
        raise ValueError("A selected municipality is missing from the Laguna boundaries")
    return selected


def grid():
    xs, ys = [], []
    for f in features():
        g = f["geometry"]
        for ring in (g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]):
            xs += [c[0] for c in ring]; ys += [c[1] for c in ring]
    w, s, e, n = transform_bounds("EPSG:4326", "EPSG:3857", min(xs) - BUFFER_DEG, min(ys) - BUFFER_DEG, max(xs) + BUFFER_DEG, max(ys) + BUFFER_DEG)
    return from_origin(w, n, PX, PX), (int((n - s) / PX), int((e - w) / PX))


def px_ha(T):
    """One pixel in ground hectares (Web Mercator metres to ground at 14.3 N)."""
    return (abs(T.a) * 0.97) ** 2 / 1e4


def barangay_raster(T, shape):
    """(features, int16 raster of barangay index + 1)."""
    feats = features()
    return feats, rasterize([(transform_geom("EPSG:4326", "EPSG:3857", f["geometry"]), i + 1) for i, f in enumerate(feats)], out_shape=shape, transform=T, dtype="int16")


def muni_crops(ids, feats):
    """{munipsgc: (r0, r1, c0, c1)} pixel windows (end exclusive) of each municipality's barangays plus CROP_PAD_PX."""
    muni_of = np.array([0] + [int(f["properties"]["munipsgc"]) for f in feats])
    out = {}
    for m in np.unique(muni_of[1:]):
        rows, cols = np.nonzero(np.isin(ids, np.flatnonzero(muni_of == m)))
        out[f"{m:010d}"] = (max(rows.min() - CROP_PAD_PX, 0), min(rows.max() + 1 + CROP_PAD_PX, ids.shape[0]), max(cols.min() - CROP_PAD_PX, 0), min(cols.max() + 1 + CROP_PAD_PX, ids.shape[1]))
    return out


def crop_corners(T, crop):
    """[[lon, lat] NW, NE, SE, SW] of a crop window."""
    from pyproj import Transformer
    to_ll = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    r0, r1, c0, c1 = crop
    return [list(to_ll.transform(*(T * (c, r)))) for c, r in ((c0, r0), (c1, r0), (c1, r1), (c0, r1))]


def muni_mask(ids, feats, munipsgc, crop):
    """Boolean mask over the crop: pixels of that municipality's barangays."""
    r0, r1, c0, c1 = crop
    idx = [i + 1 for i, f in enumerate(feats) if f["properties"]["munipsgc"] == munipsgc]
    return np.isin(ids[r0:r1, c0:c1], idx)
