"""Combine open water and the second opinions into one state per barangay and pass, then build duration runs.

A pass is flooded (1) if any source flags it, and records which sources did. It is "none seen" (0) only when no source
flags it and at least one source looked and saw nothing; with no source looking it stays unknown (-1).
Durations come only from observed passes: for a run of flooded passes,
  min days = last flooded - first flooded (the observed span)
  max days = first none-seen after - last none-seen before (null when the run touches either end of the record).
Sources differ in confidence; every run lists the sources that saw it.
Run after evidence.py: .venv/bin/python scripts/combine.py
"""
import json
from datetime import datetime

MANIFEST = "public/data/floods/manifest.json"


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


def main():
    m = json.load(open(MANIFEST))
    dates = [f["utc"] for f in m["frames"]]
    for rec in m["barangays"].values():
        votes = {"openWater": [None if s == -1 else s for s in rec["openWaterState"]], **{k: v["flagged"] for k, v in rec["evidence"].items()}}
        state, seen_by = [], []
        for i in range(len(dates)):
            hit = [k for k, v in votes.items() if v[i] == 1]
            looked = any(v[i] is not None for v in votes.values())
            state.append(1 if hit else 0 if looked else -1)
            seen_by.append(hit)
        rec["state"], rec["seenBy"], rec["episodes"] = state, seen_by, runs(state, seen_by, dates)
    m["method"]["combined"] = "flooded if any source flags the pass; none seen only if a source looked and none flagged; runs list their sources"
    json.dump(m, open(MANIFEST, "w"), separators=(",", ":"))
    for rec in m["barangays"].values():
        print(rec["name"][:14].ljust(14), [(e["first"][:10], e["last"][:10], e["minDays"], e["maxDays"], "+".join(e["seenBy"])) for e in rec["episodes"]][:6])


if __name__ == "__main__":
    main()
