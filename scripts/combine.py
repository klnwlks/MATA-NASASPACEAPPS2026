"""Combine open water and the second opinions into one state per barangay and pass, then build duration runs.

A pass is flooded (1) if any source flags it, and records which sources did. It is "none seen" (0) only when no source
flags it and at least one source looked and saw nothing; with no source looking it stays unknown (-1).
Durations come only from observed passes: for a run of flooded passes,
  min days = last flooded - first flooded (the observed span)
  max days = first none-seen after - last none-seen before (null when the run touches either end of the record).
Sources differ in confidence; every run lists the sources that saw it.
Adds state, seenBy and episodes to every barangay record of every <munipsgc>/manifest.json, and writes
public/data/floods/states.json: {<psgc>: "<one char per frame>"}, 1 flooded, 0 none seen, - unknown, in index.json frame order.
Run after flood_summary.py: .venv/bin/python scripts/combine.py --primary-only
Without --primary-only, evidence.py is included and duration ranges assume uninterrupted flooding between passes.
The primary-only mode omits those duration ranges: observations alone cannot establish continuity.
"""
import json
import sys
from datetime import datetime

from common import FLOODS

CHAR = {1: "1", 0: "0", -1: "-"}


def day(iso):
    return datetime.fromisoformat(iso[:10])


def runs(state, seen_by, dates):
    out, i, n = [], 0, len(state)
    while i < n:
        if state[i] != 1:
            i += 1
            continue
        j = i
        while j + 1 < n and state[j + 1] == 1:
            j += 1
        before = next((k for k in range(i - 1, -1, -1) if state[k] == 0), None)
        after = next((k for k in range(j + 1, n) if state[k] == 0), None)
        unknown = any(state[k] == -1 for k in range(0 if before is None else before + 1, n if after is None else after))
        out.append({"first": dates[i], "last": dates[j], "observations": j - i + 1, "minDays": (day(dates[j]) - day(dates[i])).days,
                    "maxDays": None if before is None or after is None else (day(dates[after]) - day(dates[before])).days,
                    "unknownInside": unknown, "seenBy": sorted({s for k in range(i, j + 1) for s in seen_by[k]})})
        i = j + 1
    return out


def main(primary_only=False):
    index = json.load(open(f"{FLOODS}/index.json"))
    dates = [f["utc"] for f in index["frames"]]
    states, episodes = {}, 0
    for info in index["municipalities"].values():
        path = f"{FLOODS}/{info['manifest']}"
        m = json.load(open(path))
        for psgc, rec in m["barangays"].items():
            votes = {"openWater": [None if s == -1 else s for s in rec["openWaterState"]]}
            if not primary_only:
                votes.update({k: v["flagged"] for k, v in rec.get("evidence", {}).items()})
            state, seen_by = [], []
            for i in range(len(dates)):
                hit = [k for k, v in votes.items() if v[i] == 1]
                looked = any(v[i] is not None for v in votes.values())
                state.append(1 if hit else 0 if looked else -1)
                seen_by.append(hit)
            rec["state"], rec["seenBy"] = state, seen_by
            rec["episodes"] = None if primary_only else runs(state, seen_by, dates)
            if primary_only:
                rec["evidence"] = {}
            states[psgc] = "".join(CHAR[s] for s in state)
            episodes += len(rec["episodes"] or [])
        json.dump(m, open(path, "w"), separators=(",", ":"))
    index["method"]["combined"] = ("primary-source open-water state only; duration not inferred" if primary_only else
                                   "flooded if any source flags the pass; none seen only if a source looked and none flagged; runs list their sources")
    json.dump(index, open(f"{FLOODS}/index.json", "w"), separators=(",", ":"))
    json.dump(states, open(f"{FLOODS}/states.json", "w"), separators=(",", ":"))
    print(len(states), "barangays,", len(dates), "frames,", episodes, "flooded runs;", sum(s.count("1") for s in states.values()), "flooded barangay-passes")


if __name__ == "__main__":
    main("--primary-only" in sys.argv)
