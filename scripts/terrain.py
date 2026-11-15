"""Build Terrarium-encoded raster-dem tiles from Copernicus GLO-30 for the province AOI (barangays.geojson plus buffer).

Reads the public 1x1 degree COGs by HTTP (no AWS account) and stacks the ones covering the AOI on one grid.
Run after boundaries.py: .venv/bin/python scripts/terrain.py
Output: public/data/terrain/{z}/{x}/{y}.png, public/data/terrain/tilejson.json
"""
import json
import math
import os
import shutil
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds, from_origin
from rasterio.warp import reproject
from PIL import Image
from scipy.ndimage import gaussian_filter

BUFFER_DEG = 0.08
MIN_Z, MAX_Z = 8, 12
TILE = 256
SMOOTH_SIGMA_PX = 2  # source cells (~60 m): GLO-30 is a surface model, canopy and roofs read as pixel noise
ORIGIN = 20037508.342789244
OUT = "public/data/terrain"
COG = "/vsicurl/" + "ht" + "tps://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{n}_00_{e}_00_DEM/Copernicus_DSM_COG_10_{n}_00_{e}_00_DEM.tif"  # named by south-west corner


def aoi():
    xs, ys = [], []
    for f in json.load(open("public/data/barangays.geojson"))["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for p in polys:
            for x, y in p[0]:
                xs.append(x); ys.append(y)
    return min(xs) - BUFFER_DEG, min(ys) - BUFFER_DEG, max(xs) + BUFFER_DEG, max(ys) + BUFFER_DEG


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)


def tile_bounds(x, y, z):
    s = 2 * ORIGIN / 2 ** z
    return -ORIGIN + x * s, ORIGIN - (y + 1) * s, -ORIGIN + (x + 1) * s, ORIGIN - y * s


def encode(elev):
    v = elev.astype(np.float64) + 32768.0
    r = np.floor(v / 256)
    g = np.floor(v) % 256
    b = np.floor((v - np.floor(v)) * 256)
    return np.dstack([r, g, b]).astype(np.uint8)


def mosaic(w, s, e, n):
    """GLO-30 cells are 3600 x 3600 per 1x1 degree tile at these latitudes; stack the tiles covering the AOI."""
    lons, lats = list(range(math.floor(w), math.floor(e) + 1)), list(range(math.floor(s), math.floor(n) + 1))
    out = np.full((len(lats) * 3600, len(lons) * 3600), np.nan, "float32")
    for i, lat in enumerate(reversed(lats)):
        for j, lon in enumerate(lons):
            with rasterio.open(COG.format(n=f"N{lat:02d}", e=f"E{lon:03d}")) as src:
                assert src.shape == (3600, 3600), (lat, lon, src.shape)
                out[i * 3600:(i + 1) * 3600, j * 3600:(j + 1) * 3600] = src.read(1, masked=True).astype("float32").filled(np.nan)
    return out, from_origin(lons[0], lats[-1] + 1, 1 / 3600, 1 / 3600)


w, s, e, n = aoi()
print("AOI", w, s, e, n)
data, src_transform = mosaic(w, s, e, n)
data = gaussian_filter(data, SMOOTH_SIGMA_PX, mode="nearest")
print("DEM", data.shape, "range", np.nanmin(data), np.nanmax(data))
shutil.rmtree(OUT, ignore_errors=True)  # tiles of the previous AOI must not linger
count = 0
for z in range(MIN_Z, MAX_Z + 1):
    x0, y1 = tile_xy(w, s, z)
    x1, y0 = tile_xy(e, n, z)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            tb = tile_bounds(x, y, z)
            dst = np.full((TILE, TILE), np.nan, dtype="float32")
            reproject(data, dst, src_transform=src_transform, src_crs="EPSG:4326", dst_transform=from_bounds(*tb, TILE, TILE), dst_crs="EPSG:3857", resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
            dst = np.nan_to_num(dst, nan=0.0)
            p = f"{OUT}/{z}/{x}/{y}.png"
            os.makedirs(os.path.dirname(p), exist_ok=True)
            Image.fromarray(encode(dst), "RGB").save(p, optimize=True)
            count += 1
    print("z", z, "tiles so far", count)
json.dump({"tilejson": "2.2.0", "name": "GLO-30 Terrarium", "encoding": "terrarium", "tileSize": TILE, "minzoom": MIN_Z, "maxzoom": MAX_Z, "bounds": [w, s, e, n], "tiles": ["terrain/{z}/{x}/{y}.png"]}, open(f"{OUT}/tilejson.json", "w"), indent=1)
