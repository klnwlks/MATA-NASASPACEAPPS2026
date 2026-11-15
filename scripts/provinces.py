"""Extract Philippines COD-AB v03 admin-2 boundaries for the national map.

Download the pinned HDX GDB zip named in scripts/boundaries.py to /tmp/phl_admin.gdb.zip,
then run .venv/bin/python scripts/provinces.py. The source includes Metro Manila districts;
these administrative equivalents are retained and identified by their source codes.
"""
import json
import pyogrio
from shapely import wkb
from shapely.geometry import mapping

SRC = "/vsizip//tmp/phl_admin.gdb.zip"
OUT = "public/data/provinces.geojson"

meta, _, geometries, columns = pyogrio.raw.read(SRC, layer="phl_admin2", return_fids=True)
rows = (dict(zip(meta["fields"], values)) for values in zip(*columns))
features = []
for row, raw in zip(rows, geometries):
    geom = wkb.loads(bytes(raw))
    if not geom.is_valid:
        geom = geom.buffer(0)
    geom = geom.simplify(0.0005, preserve_topology=True)
    code = str(row["adm2_pcode"])
    features.append({"type": "Feature", "id": code,
                     "properties": {"code": code, "name": row["adm2_name"], "region": row["adm1_name"],
                                    "valid_on": str(row["valid_on"]), "version": str(row["version"])},
                     "geometry": mapping(geom)})
features.sort(key=lambda feature: feature["id"])
if len({feature["id"] for feature in features}) != len(features):
    raise ValueError("Duplicate admin-2 codes in source")
with open(OUT, "w") as output:
    json.dump({"type": "FeatureCollection", "features": features}, output, separators=(",", ":"))
print(f"{len(features)} admin-2 features written to {OUT}")
