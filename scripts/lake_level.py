"""Laguna de Bay water surface elevation from satellite altimetry (DAHITI target 40866, "Bay, Lake").

Context for the replay, not a flood observation: lakeshore barangays flood when the lake rises.
Needs a DAHITI API key in .dahiti_token (git-ignored).
Run: .venv/bin/python scripts/lake_level.py
Output: public/data/floods/lake.json
"""
import json, urllib.request

TARGET, START, END = 40866, "2024-10-01", "2026-11-16"

body = json.dumps({"api_key": open(".dahiti_token").read().strip(), "dahiti_id": TARGET, "format": "json"}).encode()
req = urllib.request.Request("https://dahiti.dgfi.tum.de/api/v2/download-water-level/", body, {"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.loads(r.read())
points = [{"utc": x["datetime"].replace(" ", "T") + "Z", "m": round(x["wse"], 3), "u": round(x["wse_u"], 3)} for x in d["data"] if START <= x["datetime"][:10] <= END]
out = {"source": "DAHITI, DGFI-TUM, satellite altimetry", "target": f"{d['target_name']} ({TARGET})", "url": d["url"], "datum": "water surface elevation above the geoid, metres",
       "retrieved": d["creation_date"][:10], "points": points}
json.dump(out, open("public/data/floods/lake.json", "w"), separators=(",", ":"))
print(len(points), "points", points[0]["utc"], "->", points[-1]["utc"], "range", min(p["m"] for p in points), "-", max(p["m"] for p in points), "m")
