"""Extract COD-AB barangays for the five priority provinces, retaining original PSGC codes.

Run: .venv/bin/python scripts/priority_boundaries.py
Input: /tmp/phl_admin.gdb.zip and public/data/provinces.geojson from scripts/provinces.py.
Output: public/data/provinces/<province pcode>/barangays.geojson.
"""
import json
from pathlib import Path

import pyogrio
from shapely import wkb
from shapely.geometry import mapping, shape

SOURCE = "/vsizip//tmp/phl_admin.gdb.zip"
PRIORITIES = ("PH02015", "PH16002", "PH01055", "PH03054", "PH04034")


def main():
    with open("public/data/provinces.geojson") as f:
        provinces = {feature["id"]: feature for feature in json.load(f)["features"]}
    for code in PRIORITIES:
        bounds = shape(provinces[code]["geometry"]).bounds
        meta, _, geometries, columns = pyogrio.raw.read(SOURCE, layer="phl_admin4", bbox=bounds, return_fids=True)
        features = []
        for values, raw in zip(zip(*columns), geometries):
            row = dict(zip(meta["fields"], values))
            if row["adm2_pcode"] != code:
                continue
            psgc = str(row["adm4_pcode"]).removeprefix("PH").zfill(10)
            geom = wkb.loads(bytes(raw))
            if not geom.is_valid:
                geom = geom.buffer(0)
            geom = geom.simplify(0.00001, preserve_topology=True)
            features.append({"type": "Feature", "id": psgc,
                             "properties": {"psgc": psgc, "name": row["adm4_name"], "muni": row["adm3_name"],
                                            "munipsgc": psgc[:7] + "000", "province": code,
                                            "valid_on": str(row["valid_on"]), "version": str(row["version"])},
                             "geometry": mapping(geom)})
        features.sort(key=lambda feature: feature["id"])
        if not features or len({feature["id"] for feature in features}) != len(features):
            raise ValueError(f"Missing or duplicated barangay codes for {code}")
        path = Path("public/data/provinces") / code / "barangays.geojson"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))
        print(code, provinces[code]["properties"]["name"], len(features), flush=True)


if __name__ == "__main__":
    main()
