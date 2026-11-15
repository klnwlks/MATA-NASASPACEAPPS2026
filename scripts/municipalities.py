"""Municipality outlines for the province overview: one dissolved polygon per municipality from the barangay polygons.

Input: public/data/barangays.geojson (COD-AB v03). Output: public/data/municipalities.geojson, one feature per
municipality with {munipsgc, name, barangays, center: [lon, lat]}. The outline is the union of its barangays, simplified
by 0.0002 deg (about 20 m) and drawn as a line over the province. `center` is the pole of inaccessibility of the largest
part, so the pin and label always fall inside the municipality (a bounding-box centre can land in the lake).
Run: .venv/bin/python scripts/municipalities.py
"""
import json
from collections import defaultdict
from shapely.geometry import mapping, shape
from shapely.ops import polylabel, unary_union

SRC, OUT = "public/data/barangays.geojson", "public/data/municipalities.geojson"

groups, names = defaultdict(list), {}
for f in json.load(open(SRC))["features"]:
    p = f["properties"]
    groups[p["munipsgc"]].append(shape(f["geometry"]).buffer(0))
    names[p["munipsgc"]] = p["muni"]

features = []
for psgc in sorted(groups):
    union = unary_union(groups[psgc])
    outline = union.simplify(0.0002, preserve_topology=True)
    biggest = max(union.geoms, key=lambda g: g.area) if union.geom_type == "MultiPolygon" else union
    c = polylabel(biggest, tolerance=0.0005)
    features.append({"type": "Feature", "properties": {"munipsgc": psgc, "name": names[psgc], "barangays": len(groups[psgc]), "center": [round(c.x, 5), round(c.y, 5)]}, "geometry": mapping(outline)})
json.dump({"type": "FeatureCollection", "features": features}, open(OUT, "w"), separators=(",", ":"))
print(len(features), "municipalities")
