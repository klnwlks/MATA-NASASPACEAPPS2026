"""Per-pixel seasonal backscatter statistics from four years of Sentinel-1 over Bay, one set per track.

For every calendar month, the median and robust spread (1.4826 x MAD) of despeckled VV in dB over all pre-replay
acquisitions in that month and its two neighbours (2020-11-15 to 2024-11-14). Comparing a pass with the same season in
earlier years separates a flood from a paddy that is always flooded at that time of year, and absorbs the per-pixel
look of each track. Past floods sit inside the history too; the median and MAD keep a few of them from moving it.
Streams Planetary Computer `sentinel-1-rtc` windows on the floods.py grid; the stack lives only in memory.
Run after floods.py: .venv/bin/python scripts/history.py [track ...]
Output: /tmp/mata-floods/history_<track>.npz (median and sigma, 12 x grid, float16)
"""
import json, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from floods import PC, get, grid, to_db, warp

TRACKS = {32: "descending", 142: "ascending"}
# Four years before the replay window: enough seasons to learn the paddy cycle, short enough to stream in minutes.
# Track 142 is thin here (S1B ended Dec 2021, S1A rarely flew it), so its spread leans on SIGMA_FLOOR_DB more often.
START, END = "2020-11-15", "2024-11-14"
SIGMA_FLOOR_DB = 0.5  # a pixel that never varies would turn any change into a huge z
OUT = "/tmp/mata-floods/history_{}.npz"
# The stack is held as uint8 at 0.2 dB steps (-40 to +10.8 dB, 255 = no data) to keep it small in RAM;
# the step is well under the sigma floor. Statistics are computed in row blocks to keep float working copies small.
Q_MIN, Q_STEP, Q_NONE, ROWS = -40.0, 0.2, 255, 128


def quantise(db):
    q = np.round((db - Q_MIN) / Q_STEP)
    return np.where(np.isfinite(q), np.clip(q, 0, Q_NONE - 1), Q_NONE).astype("uint8")

def items(track, direction):
    body = {"collections": ["sentinel-1-rtc"], "datetime": f"{START}T00:00:00Z/{END}T23:59:59Z", "limit": 1000,
            "intersects": {"type": "Point", "coordinates": [121.265, 14.15]}, "query": {"sat:relative_orbit": {"eq": track}, "sat:orbit_state": {"eq": direction}}}
    return sorted(get(f"{PC}/stac/v1/search", json.dumps(body).encode())["features"], key=lambda f: f["properties"]["datetime"])


def main(only):
    transform, shape = grid()
    for track, direction in TRACKS.items():
        if only and track not in only:
            continue
        tok = get(f"{PC}/sas/v1/token/sentinel-1-rtc")["token"]  # per track: a token outlives one track's streaming, not both
        its = items(track, direction)
        months = np.array([int(f["properties"]["datetime"][5:7]) for f in its])
        with ThreadPoolExecutor(4) as ex:
            stack = np.stack(list(ex.map(lambda f: quantise(to_db(warp(f["assets"]["vv"]["href"] + "?" + tok, transform, shape))), its)))
        med = np.full((12, *shape), np.nan, "float16")
        sig = np.full((12, *shape), np.nan, "float16")
        counts = []
        for m in range(1, 13):
            sel = np.flatnonzero(np.isin(months, [(m - 2) % 12 + 1, m, m % 12 + 1]))
            counts.append(len(sel))
            for r in range(0, shape[0], ROWS):
                q = stack[sel, r:r + ROWS]
                block = np.where(q == Q_NONE, np.nan, Q_MIN + q.astype("float32") * Q_STEP)
                md = np.nanmedian(block, 0)
                med[m - 1, r:r + ROWS] = md
                sig[m - 1, r:r + ROWS] = np.maximum(1.4826 * np.nanmedian(np.abs(block - md), 0), SIGMA_FLOOR_DB)
        np.savez(OUT.format(track), median=med, sigma=sig, samples=np.array(counts), first=its[0]["properties"]["datetime"], last=its[-1]["properties"]["datetime"])
        print(track, direction, len(its), "scenes", its[0]["properties"]["datetime"][:10], "->", its[-1]["properties"]["datetime"][:10], "samples per month window", counts, flush=True)
        del stack


if __name__ == "__main__":
    main({int(a) for a in sys.argv[1:]})  # optional track numbers; default all
