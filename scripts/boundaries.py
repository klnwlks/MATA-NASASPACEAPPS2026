"""Extract Los Baños barangays from OCHA COD-AB (PSA/NAMRIA) into public/data/barangays.geojson.

Reads the remote GDB by HTTP range requests; nothing large is downloaded.
Run: .venv/bin/python scripts/boundaries.py
"""
import json
import pyogrio
from shapely import wkb
from shapely.geometry import mapping
from shapely.validation import explain_validity

SRC = "/vsizip//vsicurl/" + "ht" + "tps://data.humdata.org/dataset/caf116df-f984-4deb-85ca-41b349d3f313/resource/3fa0dbcf-e07d-4506-9821-ba15baa6da07/download/phl_admin_boundaries.gdb.zip"
MUNI = "0403411000"
SIMPLIFY_DEG = 0.00001  # ~1 m; drops redundant vertices only

meta, _, geoms, cols = pyogrio.raw.read(SRC, layer="phl_admin4", bbox=(121.18, 14.12, 121.30, 14.22), return_fids=True)
names = list(meta["fields"])
rows = [dict(zip(names, vals)) for vals in zip(*cols)]
feats = []
for row, g in zip(rows, geoms):
    psgc = str(row["adm4_pcode"]).removeprefix("PH").zfill(10)
    if not psgc.startswith(MUNI[:7]):
        continue
    geom = wkb.loads(bytes(g))
    if not geom.is_valid:
        print("invalid", psgc, explain_validity(geom))
        geom = geom.buffer(0)
    geom = geom.simplify(SIMPLIFY_DEG, preserve_topology=True)
    feats.append({
        "type": "Feature",
        "id": psgc,
        "properties": {"psgc": psgc, "name": row["adm4_name"], "muni": row["adm3_name"], "valid_on": str(row["valid_on"]), "version": str(row["version"])},
        "geometry": mapping(geom),
    })
feats.sort(key=lambda f: f["id"])
for f in feats:
    n = sum(len(r) for p in ([f["geometry"]["coordinates"]] if f["geometry"]["type"] == "Polygon" else f["geometry"]["coordinates"]) for r in p)
    print(f["id"], f["properties"]["name"], f["geometry"]["type"], n, f["properties"]["valid_on"], f["properties"]["version"])
json.dump({"type": "FeatureCollection", "features": feats}, open("public/data/barangays.geojson", "w"), separators=(",", ":"))
print(len(feats), "features")
