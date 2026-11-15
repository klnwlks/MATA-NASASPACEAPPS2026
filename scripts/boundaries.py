"""Extract the barangays of Laguna province from OCHA COD-AB (PSA/NAMRIA) into public/data/barangays.geojson.

Reads the GDB zip from /tmp/phl_admin.gdb.zip when present (about 360 MB, fetch it once from HDX), else by HTTP range
requests, which is fast for one municipality and slow for a province.
Run: .venv/bin/python scripts/boundaries.py
"""
import json, os
import pyogrio
from shapely import wkb
from shapely.geometry import mapping
from shapely.validation import explain_validity

LOCAL = "/tmp/phl_admin.gdb.zip"
REMOTE = "/vsizip//vsicurl/" + "ht" + "tps://data.humdata.org/dataset/caf116df-f984-4deb-85ca-41b349d3f313/resource/3fa0dbcf-e07d-4506-9821-ba15baa6da07/download/phl_admin_boundaries.gdb.zip"
SRC = f"/vsizip/{LOCAL}" if os.path.exists(LOCAL) else REMOTE
PROVINCE = "04034"  # Laguna: PSGC province prefix (municipality 0403402000 is Bay)
BBOX = (120.9, 13.8, 121.8, 14.7)  # coarse read window around Laguna; features are then filtered by PSGC prefix
SIMPLIFY_DEG = 0.00001  # ~1 m; drops redundant vertices only

meta, _, geoms, cols = pyogrio.raw.read(SRC, layer="phl_admin4", bbox=BBOX, return_fids=True)
names = list(meta["fields"])
rows = [dict(zip(names, vals)) for vals in zip(*cols)]
feats = []
for row, g in zip(rows, geoms):
    psgc = str(row["adm4_pcode"]).removeprefix("PH").zfill(10)
    if not psgc.startswith(PROVINCE):
        continue
    geom = wkb.loads(bytes(g))
    if not geom.is_valid:
        print("invalid", psgc, explain_validity(geom))
        geom = geom.buffer(0)
    geom = geom.simplify(SIMPLIFY_DEG, preserve_topology=True)
    feats.append({
        "type": "Feature",
        "id": psgc,
        "properties": {"psgc": psgc, "name": row["adm4_name"], "muni": row["adm3_name"], "munipsgc": psgc[:7] + "000", "valid_on": str(row["valid_on"]), "version": str(row["version"])},
        "geometry": mapping(geom),
    })
feats.sort(key=lambda f: f["id"])
munis = {}
for f in feats:
    munis.setdefault(f["properties"]["munipsgc"], [f["properties"]["muni"], 0])[1] += 1
for k, (name, n) in sorted(munis.items()):
    print(k, name, n)
json.dump({"type": "FeatureCollection", "features": feats}, open("public/data/barangays.geojson", "w"), separators=(",", ":"))
print(len(feats), "barangays in", len(munis), "municipalities")
