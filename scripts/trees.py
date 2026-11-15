"""Tree points for the 3D map from the local Protomaps extract, one file per municipality.

Two kinds, kept apart so the map can draw them differently:
  k=1  OSM `natural=tree` points, as mapped, inside the municipality plus a small buffer.
  k=0  decorative fill: seeded random points inside mapped wood, forest, reserve, park and garden polygons,
       within the municipality plus a small buffer. Not observed trees; only texture for land OSM marks as green.
Each point carries its ground elevation in metres, sampled from the app's own terrain tiles (z12), so trees sit
on the rendered surface without querying terrain at runtime.
The 300 m buffers of neighbouring municipalities overlap, so a point near a shared border can appear in both files
with the same coordinates. Each municipality has its own random stream (seed, municipality PSGC), consumed in tile order.
Run after the PMTiles extract, boundaries.py and terrain.py: .venv/bin/python scripts/trees.py
Output: public/data/trees/<munipsgc>.geojson (two MultiPoint features, coordinates [lon, lat, elevation_m])
"""
import gzip
import json
import math
import os
import mapbox_vector_tile
import numpy as np
from pmtiles.reader import MmapSource, Reader
from shapely import box, contains_xy, transform
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.prepared import prep
from PIL import Image

SRC = "public/data/basemap.pmtiles"
OUT = "public/data/trees"
BOUNDS = tuple(json.load(open("public/data/terrain/tilejson.json"))["bounds"])  # same AOI as terrain
Z, EXTENT = 15, 4096
# Fill trees per hectare by landuse kind: enough to read as canopy at z15+, small enough to ship as one file.
DENSITY = {"wood": 25, "forest": 25, "nature_reserve": 10, "park": 8, "garden": 6}
MUNI_BUFFER_DEG = 0.003  # ~300 m past the municipal line
SEED = 20261115
DEM_Z, DEM_DIR = 12, "public/data/terrain"


def tile_x(lon, n):
    return (np.asarray(lon) + 180) / 360 * n


def tile_y(lat, n):
    return (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n


def to_lonlat(tx, ty, px, py):
    n = 2 ** Z
    lon = (tx + px / EXTENT) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + py / EXTENT) / n))))
    return round(lon, 6), round(lat, 6)


_dem = {}


def elevation(lon, lat):
    """Bilinear Terrarium sample from the z12 terrain tiles, clamped at tile edges."""
    n = 2 ** DEM_Z
    fx, fy = float(tile_x(lon, n)), float(tile_y(lat, n))
    key = (int(fx), int(fy))
    if key not in _dem:
        rgb = np.asarray(Image.open(f"{DEM_DIR}/{DEM_Z}/{key[0]}/{key[1]}.png").convert("RGB"), dtype=np.float64)
        _dem[key] = rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768
    h = _dem[key]
    px, py = min((fx - key[0]) * 256 - 0.5, 254.999), min((fy - key[1]) * 256 - 0.5, 254.999)
    px, py = max(px, 0), max(py, 0)
    x0, y0 = int(px), int(py)
    dx, dy = px - x0, py - y0
    top = h[y0, x0] * (1 - dx) + h[y0, x0 + 1] * dx
    bottom = h[y0 + 1, x0] * (1 - dx) + h[y0 + 1, x0 + 1] * dx
    return round(float(top * (1 - dy) + bottom * dy), 1)


def municipalities():
    """{munipsgc: buffered polygon} in barangays.geojson order."""
    by = {}
    for f in json.load(open("public/data/barangays.geojson"))["features"]:
        by.setdefault(f["properties"]["munipsgc"], []).append(shape(f["geometry"]))
    return {m: unary_union(g).buffer(MUNI_BUFFER_DEG) for m, g in by.items()}


def main():
    n = 2 ** Z
    hectares_per_tile = (40075016.7 * math.cos(math.radians(sum(BOUNDS[1::2]) / 2)) / n) ** 2 / 1e4
    munis = municipalities()
    prepared = {m: prep(p) for m, p in munis.items()}
    rngs = {m: np.random.default_rng([SEED, int(m)]) for m in munis}
    osm = {m: {} for m in munis}
    fill = {m: [] for m in munis}
    with open(SRC, "rb") as f:
        reader = Reader(MmapSource(f))
        for tx in range(int(tile_x(BOUNDS[0], n)), int(tile_x(BOUNDS[2], n)) + 1):
            for ty in range(int(tile_y(BOUNDS[3], n)), int(tile_y(BOUNDS[1], n)) + 1):
                west, east = tx / n * 360 - 180, (tx + 1) / n * 360 - 180
                north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
                south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1) / n))))
                tile_box = box(west, south, east, north)
                here = [m for m in munis if prepared[m].intersects(tile_box)]
                if not here:
                    continue
                raw = reader.get(Z, tx, ty)
                if not raw:
                    continue
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                layers = mapbox_vector_tile.decode(raw, default_options={"y_coord_down": True})
                trees = [to_lonlat(tx, ty, *p["geometry"]["coordinates"]) for p in layers.get("pois", {}).get("features", []) if p["properties"].get("kind") == "tree" and p["geometry"]["type"] == "Point"]
                landuse = layers.get("landuse", {}).get("features", [])
                areas = {}
                for kind in DENSITY:
                    polys = [shape(g["geometry"]) for g in landuse if g["properties"].get("kind") == kind and g["geometry"]["type"] in ("Polygon", "MultiPolygon")]
                    if polys:
                        areas[kind] = unary_union(polys).buffer(0)
                for m in here:
                    if trees:
                        inside = contains_xy(munis[m], [t[0] for t in trees], [t[1] for t in trees])
                        for t, ok in zip(trees, inside):
                            if ok:
                                osm[m].setdefault(t, None)
                    local = transform(munis[m].intersection(tile_box), lambda c: np.column_stack(((tile_x(c[:, 0], n) - tx) * EXTENT, (tile_y(c[:, 1], n) - ty) * EXTENT))).intersection(box(0, 0, EXTENT, EXTENT))
                    if local.is_empty:
                        continue
                    for kind, per_ha in DENSITY.items():
                        if kind not in areas:
                            continue
                        area = areas[kind].intersection(local)
                        pts = rngs[m].uniform(0, EXTENT, size=(rngs[m].poisson(per_ha * hectares_per_tile), 2))  # this tile only: no duplicates across tiles
                        fill[m] += [to_lonlat(tx, ty, px, py) for px, py in pts[contains_xy(area, pts[:, 0], pts[:, 1])]]
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for m in munis:
        feats = [{"type": "Feature", "properties": {"k": k}, "geometry": {"type": "MultiPoint", "coordinates": [[*p, elevation(*p)] for p in pts]}} for k, pts in ((1, list(osm[m])), (0, fill[m]))]
        path = f"{OUT}/{m}.geojson"
        with open(path, "w") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))
        total += os.path.getsize(path)
        print(f"{m} {len(osm[m])} OSM trees, {len(fill[m])} fill trees, {os.path.getsize(path)} bytes")
    print(f"{len(munis)} municipalities, {total} bytes -> {OUT}/")


if __name__ == "__main__":
    main()
