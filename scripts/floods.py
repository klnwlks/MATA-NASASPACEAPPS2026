"""Classify every Sentinel-1 acquisition over Laguna province on both tracks into dry / water / flood, per 10 m pixel.

Inputs (streamed as row blocks, nothing large lands on disk except the caches below):
  - Planetary Computer `sentinel-1-rtc` (gamma0, terrain corrected with GLO-30), VV only, 2024-11-15 to 2026-11-15, descending
    track 32 and ascending track 142. Adjacent scene slices are mosaicked for each track and date.
  - A per-pixel dry-season median from February–April passes in the same replay window and track.
  - Copernicus Data Space catalogue: the list of acquisitions, so dates acquired but absent from the RTC collection are
    recorded as missing (`acquired` in grid.npz) rather than silently dropped.
  - Copernicus GLO-30 (slope mask; four 1-degree tiles N13/N14 x E120/E121, each warped and fmax-combined) and ESA WorldCover
    2021 tile N12E120 (cropland and wetland low confidence unless lake-connected; tree cover and built-up radar-blind).
Method: water is below the per-pass Otsu threshold. A flood candidate is water outside permanent water, at least 3 dB
darker than the dry-season median and on slopes under 5 degrees. Isolated cropland or wetland water is low confidence.
The classification is repeated with looser and stricter thresholds for hectare ranges. The four-year seasonal baseline
is deferred, so seasonal agricultural changes may be misclassified as flood. This implementation is specific to Laguna;
its permanent-water connectivity must not be reused as a generic river connectivity model for other provinces.

Phase A, per track: stream every Feb-Apr pass of the window, per-pass Otsu threshold, running count for `permanent` (at least
80 % of the dry passes below their threshold), `ref` = per-pixel median over the dry passes, lake = largest permanent
component. Written as soon as a track finishes: CACHE/ref_<track>.npy (float16 dB) and the keys permanent_<track>,
lake_<track>, lake (union of the lakes so far) in grid.npz. Resumable per dry pass (CACHE/dry_<track>/, deleted when done).
Phase B, every pass in time order (both tracks interleaved, scenes prefetched in a thread pool): the dry-season change rule
for base / LOOSE / STRICT, the class raster to CACHE/cls/<YYYYMMDD>_<track>.npz, and per-barangay
numbers accumulated into CACHE/stats.npz. A pass whose cls file exists is skipped (its numbers are re-read from that file).

Files written (CACHE = common.CACHE, atomically via rename):
  grid.npz   transform (6), shape, psgc (barangay order), dates (UTC iso, all RTC passes), platforms, tracks, thresholds (nan until
             classified), dry_season (UTC iso of the Feb-Apr passes), acquired ("YYYYMMDD:platform:track"), then per track
             permanent_<track> and lake_<track>, and lake: np.packbits of the flattened (H, W) bool raster.
  cls/<YYYYMMDD>_<track>.npz   c: uint8 (H, W) class raster (see common.py); also this pass's rows high, low, visible, strict,
             loose (n_barangays + 1, column 0 = outside any barangay), thr, utc, platform.
  stats.npz  high, low, strict, loose (hectares: FLOOD pixels / FLOOD_LOW pixels / flood minus low confidence under the strict and
             loose rules), visible (share of the barangay's pixels that are neither NODATA nor BLIND), each (passes, n_barangays + 1);
             dates (UTC iso), platforms, tracks, thresholds. Passes are sorted by UTC time.
  S1CORE_STATUS.txt  progress and ETA.
Run: .venv/bin/python scripts/floods.py [track ...]. No historical normalization is required.
"""
import json, os, shutil, sys, threading, time, urllib.parse, urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import numpy as np, rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import Window, from_bounds
from scipy.ndimage import gaussian_filter, label, uniform_filter

from common import CACHE, PROVINCE, START, END, TRACKS, PX, NODATA, DRY, PERMANENT, FLOOD, FLOOD_LOW, BLIND, barangay_raster, features, grid, px_ha

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("GDAL_CACHEMAX", "200")  # MB, shared by all reader threads (default is 5 % of RAM)
PC = "https://planetarycomputer.microsoft.com/api"
CDSE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?"
DEM_TILES = [f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{la}_00_E{lo}_00_DEM/Copernicus_DSM_COG_10_N{la}_00_E{lo}_00_DEM.tif"
             for la in (13, 14) for lo in (120, 121)]
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif"
Z_THR, DROP_DB, MAX_SLOPE_DEG, PERMANENT_SHARE = -2.0, 3.0, 5.0, 0.8
# Sensitivity for hectare ranges: (water threshold shift dB, z threshold, dry-season drop dB) for loose and strict.
BASE, LOOSE, STRICT = (0.0, Z_THR, DROP_DB), (1.0, -1.5, 2.0), (-1.0, -2.5, 4.0)
DEM_SMOOTH_PX = 6  # about 60 m, as in terrain.py
ACQUIRED_POINT = (121.32, 14.28)  # province centre, for the CDSE catalogue
# History is stored as uint8: median at Q_STEP dB from Q_MIN (255 = no data), sigma at SIG_STEP dB (clip 12.7 dB, 255 = no data).
Q_MIN, Q_STEP, Q_NONE, SIG_STEP = -40.0, 0.2, 255, 0.05
ROWS, PAD = 500, 3  # row block of a streamed scene, and the pad of the 5 x 5 boxcar
CHUNK = 256  # rows per working chunk in the per-pass arithmetic
PREFETCH = int(os.environ.get("S1_PREFETCH", 3))  # scenes in flight or waiting, each about 100 MB as float16


def get(url, data=None, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))


class Sas:
    """Planetary Computer SAS token, refreshed 15 minutes before it expires, shared by all threads."""
    def __init__(self):
        self.lock, self.token, self.until = threading.Lock(), None, 0.0

    def __call__(self):
        with self.lock:
            if time.time() >= self.until:
                r = get(f"{PC}/sas/v1/token/sentinel-1-rtc")
                self.token = r["token"]
                exp = r.get("msft:expiry")
                self.until = (datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp() if exp else time.time() + 3000) - 900
            return self.token


def province_bbox(T, shape):
    return transform_bounds("EPSG:3857", "EPSG:4326", T.c, T.f - shape[0] * PX, T.c + shape[1] * PX, T.f)


def rtc_items(track, direction, start, end, bbox):
    """Group adjacent RTC slices from the same track and date into one observation."""
    body = {"collections": ["sentinel-1-rtc"], "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 1000, "bbox": list(bbox),
            "query": {"sat:relative_orbit": {"eq": track}, "sat:orbit_state": {"eq": direction}}}
    items = sorted(get(f"{PC}/stac/v1/search", json.dumps(body).encode())["features"], key=lambda f: f["properties"]["datetime"])
    groups = []
    for item in items:
        day = item["properties"]["datetime"][:10]
        if not groups or groups[-1]["properties"]["datetime"][:10] != day:
            groups.append({**item, "slices": [item]})
        else:
            groups[-1]["slices"].append(item)
    return groups


def _warp(src, Tb, shape, resampling=Resampling.bilinear, dtype="float32"):
    """Warp the part of an open raster covering (Tb, shape) in EPSG:3857 onto that window."""
    dst = np.full(shape, np.nan if dtype == "float32" else 0, dtype)
    b = transform_bounds("EPSG:3857", src.crs, Tb.c, Tb.f - shape[0] * PX, Tb.c + shape[1] * PX, Tb.f)
    win = from_bounds(*b, src.transform).round_offsets().round_lengths()
    win = Window(win.col_off - 2, win.row_off - 2, win.width + 4, win.height + 4)  # resampling margin
    if win.col_off >= src.width or win.row_off >= src.height or win.col_off + win.width <= 0 or win.row_off + win.height <= 0:
        return dst  # the window lies wholly outside this raster (DEM tiles)
    inside = win.col_off >= 0 and win.row_off >= 0 and win.col_off + win.width <= src.width and win.row_off + win.height <= src.height
    a = src.read(1, window=win, boundless=not inside, fill_value=0).astype(dtype)
    if dtype == "float32":
        a[a <= 0] = np.nan
    reproject(a, dst, src_transform=src.window_transform(win), src_crs=src.crs, dst_transform=Tb, dst_crs="EPSG:3857", resampling=resampling, src_nodata=np.nan if dtype == "float32" else None)
    return dst


def warp(path, Tb, shape, resampling=Resampling.bilinear, dtype="float32", tries=5):
    # Hundreds of windows meet DNS blips and dropped connections; one must not end the run.
    for attempt in range(tries):
        try:
            with rasterio.open(path) as src:
                return _warp(src, Tb, shape, resampling, dtype)
        except rasterio.errors.RasterioError:
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))


def to_db(a, k=5):  # boxcar despeckle in linear power, then dB
    ok = np.isfinite(a)
    num, den = uniform_filter(np.where(ok, a, 0), k), uniform_filter(ok.astype("float32"), k)
    return np.where(ok, 10 * np.log10(np.maximum(num, 1e-6) / np.maximum(den, 1e-6)), np.nan).astype("float32")


def block_db(src, T, W, r0, r1):
    """Despeckled VV in dB of rows r0:r1 of the grid, read with PAD extra rows so the boxcar is exact at the block edges."""
    n = r1 - r0 + 2 * PAD
    a = _warp(src, T * Affine.translation(0, r0 - PAD), (n, W))
    return to_db(a)[PAD:PAD + r1 - r0]


def read_blocks(item, sas, T, shape, spans, tries=6):
    """Mosaic each observation's slices in linear power before despeckling; uncovered pixels remain NaN."""
    sources = []
    try:
        for r0, r1 in spans:
            for attempt in range(tries):
                try:
                    if not sources:
                        for part in item.get("slices", [item]):
                            sources.append(rasterio.open(part["assets"]["vv"]["href"] + "?" + sas()))
                    n = r1 - r0 + 2 * PAD
                    transform = T * Affine.translation(0, r0 - PAD)
                    mosaic = np.full((n, shape[1]), np.nan, "float32")
                    for src in sources:
                        a = _warp(src, transform, mosaic.shape)
                        np.copyto(mosaic, a, where=~np.isfinite(mosaic) & np.isfinite(a))
                    yield r0, r1, to_db(mosaic)[PAD:PAD + r1 - r0]
                    break
                except rasterio.errors.RasterioError:
                    for src in sources:
                        src.close()
                    sources = []
                    if attempt == tries - 1:
                        raise
                    time.sleep(10 * (attempt + 1))
    finally:
        for src in sources:
            src.close()


def load_scene(item, sas, T, shape):
    out = np.empty(shape, "float16")
    for r0, r1, blk in read_blocks(item, sas, T, shape, [(r, min(r + ROWS, shape[0])) for r in range(0, shape[0], ROWS)]):
        out[r0:r1] = blk
    return out


def quantise(db):
    q = np.round((db - Q_MIN) / Q_STEP)
    return np.where(np.isfinite(q), np.clip(q, 0, Q_NONE - 1), Q_NONE).astype("uint8")


def median_pair(srt, cnt):
    """srt: (..., k) sorted ascending with the largest value as the no-data sentinel at the end; cnt: valid count per pixel.
    Returns lo + hi of the middle pair (the median is half of it; equal when the count is odd). Garbage where cnt == 0."""
    lo = np.maximum(cnt - 1, 0) // 2
    hi = cnt // 2
    take = lambda i: np.take_along_axis(srt, i[..., None], -1)[..., 0].astype("int32")
    return take(lo) + take(hi)


def otsu(s):
    """Otsu threshold of a float16 raster, chunked; identical to np.histogram(finite values, 200) + the same criterion."""
    lo, hi = np.inf, -np.inf
    for a in range(0, s.shape[0], CHUNK):
        x = s[a:a + CHUNK].astype("float32")
        x = x[np.isfinite(x)]
        if x.size:
            lo, hi = min(lo, float(x.min())), max(hi, float(x.max()))
    h = np.zeros(200, "int64")
    for a in range(0, s.shape[0], CHUNK):
        x = s[a:a + CHUNK].astype("float32")
        h += np.histogram(x[np.isfinite(x)], 200, range=(lo, hi))[0]
    edges = np.linspace(lo, hi, 201)
    c = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(h); w1 = w0[-1] - w0
    m0 = np.cumsum(h * c) / np.maximum(w0, 1); m1 = (np.sum(h * c) - np.cumsum(h * c)) / np.maximum(w1, 1)
    return float(c[np.argmax(w0 * w1 * (m0 - m1) ** 2)])


def acquisitions(track):
    flt = (f"Collection/Name eq 'SENTINEL-1' and OData.CSC.Intersects(area=geography'SRID=4326;POINT({ACQUIRED_POINT[0]} {ACQUIRED_POINT[1]})') and "
           "Attributes/OData.CSC.StringAttribute/any(a:a/Name eq 'productType' and a/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S') and "
           f"Attributes/OData.CSC.IntegerAttribute/any(a:a/Name eq 'relativeOrbitNumber' and a/OData.CSC.IntegerAttribute/Value eq {track}) and "
           f"ContentDate/Start gt {START}T00:00:00.000Z and ContentDate/Start lt {END}T00:00:00.000Z")
    names = [p["Name"] for p in get(CDSE + urllib.parse.urlencode({"$filter": flt, "$top": 1000}))["value"]]
    return sorted({(n[17:25], n[:3], track) for n in names})  # (YYYYMMDD, platform, track)


def atomic_savez(path, compressed=False, **arrays):
    tmp = f"{path}.tmp.npz"
    (np.savez_compressed if compressed else np.savez)(tmp, **arrays)
    os.replace(tmp, path)


def update_grid(**arrays):
    """Add or replace keys in grid.npz (single writer, so read-modify-write with an atomic rename is safe)."""
    path = f"{CACHE}/grid.npz"
    cur = {}
    if os.path.exists(path):
        with np.load(path) as d:
            cur = {k: d[k] for k in d.files}
    cur.update(arrays)
    atomic_savez(path, True, **cur)


def static_layers(T, shape):
    """steep, low_conf, blind bool rasters. Cached in CACHE/static.npz (packed). DEM is warped tile by tile in row blocks."""
    path, H, W = f"{CACHE}/static.npz", shape[0], shape[1]
    if os.path.exists(path):
        with np.load(path) as d:
            return tuple(np.unpackbits(d[k], count=H * W).reshape(shape).astype(bool) for k in ("steep", "low_conf", "blind"))
    steep, low_conf, blind = (np.zeros(shape, bool) for _ in range(3))
    pad, step = 30, 1000  # the 6 px smoothing reaches 4 sigma = 24 px, plus the gradient
    for r0 in range(0, H, step):
        r1 = min(r0 + step, H)
        Tb, n = T * Affine.translation(0, r0 - pad), r1 - r0 + 2 * pad
        d = None
        for tile in DEM_TILES:
            w = warp(tile, Tb, (n, W))
            d = w if d is None else np.fmax(d, w)
        # Smooth the 30 m surface model first: raw, its tree and roof edges read as steep slopes across flat paddies.
        d = gaussian_filter(np.nan_to_num(d), DEM_SMOOTH_PX)
        gy, gx = np.gradient(d, PX * 0.97)  # mercator to ground scale at 14.3 N
        steep[r0:r1] = (np.degrees(np.arctan(np.hypot(gx, gy))) >= MAX_SLOPE_DEG)[pad:pad + r1 - r0]
        lc = warp(WC, T * Affine.translation(0, r0), (r1 - r0, W), Resampling.nearest, "uint8")
        low_conf[r0:r1] = np.isin(lc, (40, 90, 95))  # cropland, herbaceous wetland, mangroves
        blind[r0:r1] = np.isin(lc, (10, 50))  # tree cover, built-up
        print("static rows", r1, "/", H, flush=True)
    atomic_savez(path, True, steep=np.packbits(steep), low_conf=np.packbits(low_conf), blind=np.packbits(blind))
    return steep, low_conf, blind


class Prefetch:
    """Iterate (job, scene) in order while a thread pool loads the next PREFETCH scenes (in flight or waiting)."""
    def __init__(self, jobs, load):
        self.jobs, self.load, self.ex, self.q = list(jobs), load, ThreadPoolExecutor(PREFETCH), deque()
        self.i = 0

    def _fill(self):
        while self.i < len(self.jobs) and len(self.q) < PREFETCH:
            self.q.append((self.jobs[self.i], self.ex.submit(self.load, self.jobs[self.i])))
            self.i += 1

    def __iter__(self):
        self._fill()
        while self.q:
            job, fut = self.q.popleft()
            scene = fut.result()
            self._fill()
            yield job, scene
        self.ex.shutdown()


class Status:
    def __init__(self):
        self.t0, self.log = time.time(), {}

    def write(self, phase, done, total, note=""):
        el = time.time() - self.t0
        eta = f"{el / max(done, 1) * (total - done) / 3600:.1f} h" if done else "unknown"
        txt = f"S1Core floods.py {phase}\nstarted {datetime.fromtimestamp(self.t0):%Y-%m-%d %H:%M}, updated {datetime.now():%Y-%m-%d %H:%M}\n{done}/{total} done in this run segment; elapsed {el / 3600:.2f} h, ETA {eta}\n{note}\n"
        with open(f"{CACHE}/S1CORE_STATUS.txt", "w") as f:
            f.write(txt)


def date_of(item):
    return item["properties"]["datetime"][:10]


def phase_a(track, items, T, shape, sas, status):
    """Dry-season references for one track; see module docstring. Returns nothing, writes ref_<track>.npy and grid.npz keys."""
    H, W = shape
    dry = [f for f in items if date_of(f)[5:7] in ("02", "03", "04")]
    d = f"{CACHE}/dry_{track}"
    os.makedirs(d, exist_ok=True)
    name = lambda f: date_of(f).replace("-", "")
    todo = [f for f in dry if not os.path.exists(f"{d}/{name(f)}.json")]

    def load(f):
        return load_scene(f, sas, T, shape)

    for k, (f, s) in enumerate(Prefetch(todo, load)):
        thr = otsu(s)
        q = np.lib.format.open_memmap(f"{d}/{name(f)}.q.tmp.npy", "w+", "uint8", (H, W))
        for a in range(0, H, CHUNK):
            q[a:a + CHUNK] = quantise(s[a:a + CHUNK].astype("float32"))
        q.flush(); del q
        os.replace(f"{d}/{name(f)}.q.tmp.npy", f"{d}/{name(f)}.q.npy")
        np.save(f"{d}/{name(f)}.below.npy", np.packbits(s < thr))
        json.dump({"thr": thr}, open(f"{d}/{name(f)}.json", "w"))  # written last: its presence marks the pass done
        status.write(f"phase A track {track}", k + 1, len(todo), f"dry pass {name(f)} threshold {thr:.2f} dB")
        print("A", track, name(f), f"thr {thr:.2f}", flush=True)
    n = len(dry)
    if n:
        count = np.zeros(H * W, "uint8")
        for f in dry:
            count += np.unpackbits(np.load(f"{d}/{name(f)}.below.npy"), count=H * W)
        permanent = (count / n >= PERMANENT_SHARE).reshape(shape)
        del count
        ref = np.lib.format.open_memmap(f"{CACHE}/ref_{track}.tmp.npy", "w+", "float16", (H, W))
        qs = [np.load(f"{d}/{name(f)}.q.npy", mmap_mode="r") for f in dry]
        for a in range(0, H, 64):
            qt = np.ascontiguousarray(np.stack([x[a:a + 64] for x in qs], -1))
            cnt = (qt != Q_NONE).sum(-1)
            m2 = median_pair(np.sort(qt, -1, kind="stable"), cnt)  # lo + hi in 0.2 dB steps from Q_MIN
            ref[a:a + 64] = np.where(cnt > 0, Q_MIN + m2 * (Q_STEP / 2), np.nan)
        ref.flush(); del ref, qs
        os.replace(f"{CACHE}/ref_{track}.tmp.npy", f"{CACHE}/ref_{track}.npy")
        lab, _ = label(permanent)
        lake = lab == np.bincount(lab[lab > 0]).argmax()  # Laguna de Bay: the largest permanent water body
        del lab
    else:  # no dry-season pass on this track: no reference, no permanent water, no lake
        permanent = lake = np.zeros(shape, bool)
        np.save(f"{CACHE}/ref_{track}.npy", np.full(shape, np.nan, "float16"))
    other = np.unpackbits(np.load(f"{CACHE}/grid.npz")["lake"], count=H * W).astype(bool).reshape(shape) if os.path.exists(f"{CACHE}/grid.npz") and "lake" in np.load(f"{CACHE}/grid.npz").files else 0
    update_grid(**{f"permanent_{track}": np.packbits(permanent), f"lake_{track}": np.packbits(lake), "lake": np.packbits(lake | other)})
    shutil.rmtree(d)
    print("A", track, "done:", n, "dry passes;", int(permanent.sum()), "permanent px,", int(lake.sum()), "lake px", flush=True)


def per_barangay(mask, ids, n):
    out = np.zeros(n + 1)
    for a in range(0, mask.shape[0], CHUNK):
        out += np.bincount(ids[a:a + CHUNK][mask[a:a + CHUNK]], minlength=n + 1)
    return out


def classify(s, thr, month, t, st):
    """Classify against this track's replay-window dry-season reference, without historical normalization."""
    steep, low_conf, blind = st
    perm, lake, ref = t["perm"], t["lake"], t["ref"]
    H, W = s.shape
    lake_any = bool(lake.any())

    def flood(shift, zthr, drop, want_nodata=False):
        # A same-track dry-season reference within the replay window is the only baseline in this run.
        # Isolated cropland and wetlands remain low-confidence because paddies can resemble flood water.
        cand, nodata = np.empty(s.shape, bool), np.empty(s.shape, bool)
        for a in range(0, H, CHUNK):
            b = min(a + CHUNK, H)
            sc = s[a:b].astype("float32")
            baseline = ref[a:b].astype("float32")
            cand[a:b] = (sc < thr + shift) & ~perm[a:b] & ~steep[a:b] & (sc - baseline <= -drop)
            nodata[a:b] = ~np.isfinite(sc) | ~np.isfinite(baseline) | (steep[a:b] & ~perm[a:b])
        if lake_any:
            lab, _ = label(cand | lake)
            linked = cand & np.isin(lab, np.unique(lab[lake]))
            f = linked | (cand & seasonal)
            return f, f & low_conf & ~linked  # isolated cropland or wetland water stays low confidence

        for i, d in enumerate(dates):
            s = stack[i].astype("float32")
            m = int(d[5:7]) - 1
            z = (s - hist["median"][m].astype("float32")) / hist["sigma"][m].astype("float32")
            f, low = flood(s, z, thr[i], 0.0, Z_THR, DROP_DB)
            c = np.full(shape, DRY, "uint8")
            c[f] = FLOOD
            c[low] = FLOOD_LOW
            c[blind & ~f] = BLIND
            c[permanent] = PERMANENT
            c[~np.isfinite(s) | ~np.isfinite(z) | (steep & ~permanent)] = NODATA
            variants = [np.packbits(v[0] & ~v[1]) for v in (flood(s, z, thr[i], *LOOSE), flood(s, z, thr[i], *STRICT))]
            rows.append((d, platforms[i], track, c, *variants, thr[i]))
        del stack
    rows.sort(key=lambda r: r[0])
    np.savez_compressed(f"{OUT}/classes.npz", classes=np.stack([r[3] for r in rows]), loose=np.stack([r[4] for r in rows]), strict=np.stack([r[5] for r in rows]),
                        dates=np.array([r[0] for r in rows]), platforms=np.array([r[1] for r in rows]), tracks=np.array([r[2] for r in rows]),
                        thresholds=np.array([r[6] for r in rows]), transform=np.array(transform)[:6], dry_season=np.array(sorted(dry_ref)),
                        acquired=np.array([f"{d}:{p}:{t}" for t in tracks for d, p, _ in acquisitions(t)]))
    print(len(rows), "passes classified;", len(dry_ref), "dry-season reference passes")


if __name__ == "__main__":
    main({int(a) for a in sys.argv[1:]})  # optional track numbers; default all
