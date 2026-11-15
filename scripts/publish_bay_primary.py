"""Publish the existing Bay primary-source replay without its former second opinions.

Input: /tmp/mata-floods/classes_old.npz and manifest_old.json from the original Bay run.
This is an early result while the larger two-year primary-source processing runs. It does not
invent sensitivity ranges or durations absent from that cache. Other barangays remain unknown.
Run: .venv/bin/python scripts/publish_bay_primary.py
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from flood_summary import PALETTE

CACHE = Path('/tmp/mata-floods')
OUT = Path('public/data/floods')
MUNI = '0403402000'


def main():
    with (CACHE / 'manifest_old.json').open() as f:
        old = json.load(f)
    with open('public/data/barangays.geojson') as f:
        feats = [f for f in json.load(f)['features'] if f['properties']['munipsgc'] == MUNI]
    z = np.load(CACHE / 'classes_old.npz')
    classes, transform = z['classes'], Affine(*z['transform'])
    if len(classes) != len(old['frames']) or set(old['barangays']) != {f['properties']['psgc'] for f in feats}:
        raise ValueError('Bay geometry, manifest, and class stack do not match')
    mask = rasterize([(transform_geom('EPSG:4326', 'EPSG:3857', f['geometry']), 1) for f in feats],
                     out_shape=classes.shape[1:], transform=transform).astype(bool)
    folder = OUT / MUNI
    folder.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, frame in enumerate(old['frames']):
        if str(z['dates'][i])[:19] != frame['utc'][:19]:
            raise ValueError(f'Pass mismatch at {i}')
        name = frame['utc'][:10].replace('-', '') + '_32.png'
        c = classes[i].copy()
        c[~mask] = 255
        image = Image.fromarray(c, 'P')
        palette = [0] * (256 * 4)
        for k, rgba in PALETTE.items():
            palette[k * 4:k * 4 + 4] = rgba
        image.putpalette(palette, 'RGBA')
        image.save(folder / name, compress_level=6)
        frames.append({**{k: frame[k] for k in ('utc', 'platform', 'thresholdDb', 'daysSincePrevious')},
                       'id': name[:-4], 'track': 32, 'file': f'{MUNI}/{name}'})
    records, states = {}, {}
    for psgc, rec in old['barangays'].items():
        state = rec['openWaterState']
        if len(state) != len(frames):
            raise ValueError(f'Pass count mismatch for {psgc}')
        states[psgc] = ''.join('-' if s == -1 else str(s) for s in state)
        records[psgc] = {k: rec[k] for k in ('name', 'areaHa', 'noiseHa', 'floodHa', 'lowConfidenceHa', 'visibleShare', 'openWaterState')}
        records[psgc].update(state=state, seenBy=[['openWater'] if s == 1 else [] for s in state], evidence={}, episodes=None)
    manifest = {'barangays': records, 'frames': frames, 'corners': old['corners']}
    index = {'window': old['window'], 'coverageNote': 'Early observations: Bay, Laguna only', 'frames': frames, 'tracks': {'32': 'Sentinel-1 descending relative orbit 32'},
             'municipalities': {MUNI: {'name': 'Bay', 'corners': old['corners'], 'barangays': sorted(records), 'manifest': f'{MUNI}/manifest.json'}},
             'method': {k: v for k, v in old['method'].items() if k in ('reference', 'water', 'flood', 'lowConfidence', 'radarBlind', 'barangayFlooded', 'minVisibleShare')}}
    for path, data in ((folder / 'manifest.json', manifest), (OUT / 'states.json', states), (OUT / 'index.json', index)):
        with path.open('w') as f:
            json.dump(data, f, separators=(',', ':'))
    print(f'{len(frames)} Sentinel-1 track 32 passes, {len(records)} Bay barangays; all other barangays unknown')


if __name__ == '__main__':
    main()
