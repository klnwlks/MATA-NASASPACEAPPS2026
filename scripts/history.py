"""Stream same-track seasonal Sentinel-1 history on the Laguna grid.

Run: .venv/bin/python scripts/history.py [32 142]
Writes resumable uint8 median and MAD arrays under common.CACHE; 255 denotes no data.
"""
import json
import os
import sys
import warnings
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from common import CACHE, TRACKS, grid
from floods import Q_MIN, Q_STEP, Q_NONE, SIG_STEP, Sas, province_bbox, quantise, read_blocks, rtc_items

START, END = "2020-11-15", "2024-11-14"
BLOCK_ROWS, CALC_ROWS, WORKERS = 128, 16, 3


def main(only):
    os.makedirs(CACHE, exist_ok=True)
    T, shape = grid()
    sas = Sas()
    for track, direction in TRACKS.items():
        if only and track not in only:
            continue
        items = rtc_items(track, direction, START, END, province_bbox(T, shape))
        if not items:
            raise RuntimeError(f"No historic acquisitions for track {track}")
        months = np.array([int(f["properties"]["datetime"][5:7]) for f in items])
        paths = [f"{CACHE}/history_{track}_{name}.npy" for name in ("med", "sig")]
        progress = f"{CACHE}/history_{track}.progress.json"
        signature = [f["id"] for f in items]
        if os.path.exists(progress):
            with open(progress) as f:
                state = json.load(f)
            if state["items"] != signature or state["shape"] != list(shape):
                raise RuntimeError(f"History inputs changed; remove {progress} and its arrays before restarting")
            arrays = [np.load(p, mmap_mode="r+") for p in paths]
        else:
            arrays = [np.lib.format.open_memmap(p, mode="w+", dtype="uint8", shape=(12, *shape)) for p in paths]
            state = {"items": signature, "shape": list(shape), "rows": 0}
        med, sig = arrays
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for r0 in range(state["rows"], shape[0], BLOCK_ROWS):
                r1 = min(r0 + BLOCK_ROWS, shape[0])
                started = time.monotonic()
                print(f"track {track}: loading rows {r0}:{r1}, {len(items)} acquisitions", flush=True)
                def load(item):
                    return quantise(next(read_blocks(item, sas, T, shape, [(r0, r1)]))[2])
                stack = np.empty((len(items), r1 - r0, shape[1]), dtype="uint8")
                futures = {pool.submit(load, item): i for i, item in enumerate(items)}
                for done, future in enumerate(as_completed(futures), 1):
                    i = futures[future]
                    stack[i] = future.result()
                    print(f"track {track}: rows {r0}:{r1}, acquisition {done}/{len(items)} "
                          f"({items[i]['properties']['datetime'][:10]}), {time.monotonic() - started:.0f}s", flush=True)
                for m in range(1, 13):
                    sel = np.flatnonzero(np.isin(months, [(m - 2) % 12 + 1, m, m % 12 + 1]))
                    if not len(sel):
                        med[m - 1, r0:r1] = Q_NONE
                        sig[m - 1, r0:r1] = Q_NONE
                        continue
                    for a in range(0, r1 - r0, CALC_ROWS):
                        b = min(a + CALC_ROWS, r1 - r0)
                        q = stack[sel, a:b]
                        block = np.where(q == Q_NONE, np.nan, Q_MIN + q.astype("float32") * Q_STEP)
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", RuntimeWarning)
                            md = np.nanmedian(block, axis=0)
                            sd = np.maximum(1.4826 * np.nanmedian(np.abs(block - md), axis=0), 0.5)
                        med[m - 1, r0+a:r0+b] = quantise(md)
                        sig[m - 1, r0+a:r0+b] = np.where(np.isfinite(sd), np.clip(np.rint(sd / SIG_STEP), 0, 254), Q_NONE).astype("uint8")
                med.flush()
                sig.flush()
                state["rows"] = r1
                with open(progress + ".tmp", "w") as f:
                    json.dump(state, f)
                os.replace(progress + ".tmp", progress)
                print(f"track {track}: {r1}/{shape[0]} rows; {len(items)} acquisitions", flush=True)
        with open(f"{CACHE}/history_{track}.done", "w") as f:
            json.dump(state, f)


if __name__ == "__main__":
    main({int(a) for a in sys.argv[1:]})
