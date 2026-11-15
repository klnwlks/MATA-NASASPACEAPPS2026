import { FARM_PATTERN } from './farmPattern.js'

export const SCHEMATIC_HEIGHT_M = 6
export const TERRAIN_EXAGGERATION = 1.4
export const HOME_VIEW = { bearing: 180, pitch: 62 } // municipality drill-down, looking south from the lake
export const PROVINCE_VIEW = { bearing: 180, pitch: 45 } // overview: flatter, so 682 barangays stay legible

const C = { land: '#F2EFE0', lake: '#5C95F2', park: '#8ED9AF', forest: '#3E9B5A', road: '#E8807F', farm: '#CFE08A', town: '#EFE4CF' }
const FARM = ['in', ['get', 'kind'], ['literal', ['farmland', 'farmyard', 'orchard']]]
const kind = (...k) => ['in', ['get', 'kind'], ['literal', k]]
// Base-2 growth keeps a road's on-screen width proportional to the ground it covers.
const width = (z12, z18) => ['interpolate', ['exponential', 2], ['zoom'], 12, z12, 18, z18]
const ROUND = { 'line-cap': 'round', 'line-join': 'round' }
const ROOF_M = 0.4
const HEIGHT = ['coalesce', ['get', 'height'], SCHEMATIC_HEIGHT_M]
const BUILDING = ['==', ['get', 'kind'], 'building']
const AOI = [120.925, 13.883, 121.715, 14.676] // province terrain and basemap bounds, rounded outward
// [layer id, filter, representative height in m]: one shadow offset per height band (see sun.js).
export const SHADOW_BUCKETS = [
  ['building-shadow-low', ['<', HEIGHT, 10], 6],
  ['building-shadow-mid', ['all', ['>=', HEIGHT, 10], ['<', HEIGHT, 25]], 15],
  ['building-shadow-high', ['>=', HEIGHT, 25], 35],
]
// Draped layers are cached in terrain textures that re-render once per change; a paint transition would freeze mid-fade.
const NOW = { duration: 0, delay: 0 }

const dem = (root) => ({ type: 'raster-dem', encoding: 'terrarium', tileSize: 256, minzoom: 8, maxzoom: 12, tiles: [`${root}data/terrain/{z}/{x}/{y}.png`], bounds: AOI })

// Served from this origin with no keys, except the optional EOX imagery, which degrades to vector colours offline.
export function buildStyle(origin) {
  const root = `${origin}${import.meta.env.BASE_URL}`
  return {
    version: 8,
    glyphs: `${root}fonts/{fontstack}/{range}.pbf`,
    sources: {
      base: { type: 'vector', url: `pmtiles://${root}data/basemap.pmtiles` },
      dem: dem(root),
      shade: dem(root), // MapLibre advises a separate source for hillshade and terrain
      // Sentinel-2 cloudless 2024 by EOX: CC BY-NC-SA 4.0, non-commercial only. A 2024 composite, not storm-date imagery.
      imagery: { type: 'raster', tileSize: 256, maxzoom: 15, bounds: AOI, tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg'] },
      night: { type: 'geojson', data: { type: 'Feature', id: 1, properties: {}, geometry: { type: 'Polygon', coordinates: [[[AOI[0] - 0.5, AOI[1] - 0.5], [AOI[2] + 0.5, AOI[1] - 0.5], [AOI[2] + 0.5, AOI[3] + 0.5], [AOI[0] - 0.5, AOI[3] + 0.5], [AOI[0] - 0.5, AOI[1] - 0.5]]] } } },
    },
    terrain: { source: 'dem', exaggeration: TERRAIN_EXAGGERATION },
    // Low intensity keeps walls bright plaster instead of muddy; faces still read by direction.
    light: { anchor: 'map', color: '#FFFFFF', intensity: 0.25, position: [1.2, 210, 30] },
    // Warm haze toward the horizon so steep pitches read as a landscape, not a cut-off sheet.
    sky: { 'sky-color': '#9CC7EA', 'horizon-color': '#F5E6C8', 'fog-color': '#EFE8D6', 'sky-horizon-blend': 0.6, 'horizon-fog-blend': 0.7, 'fog-ground-blend': 0.35, 'atmosphere-blend': 0 },
    layers: [
      { id: 'land', type: 'background', paint: { 'background-color': C.land } },
      { id: 'relief', type: 'color-relief', source: 'shade', paint: { 'color-relief-color': ['interpolate', ['linear'], ['elevation'], 0, '#F2EFE0', 15, '#E9ECC6', 60, '#CFE29B', 200, '#9FD184', 450, '#66B86A', 800, '#3E9B5A', 1100, '#2B7D49'] } },
      { id: 'hillshade', type: 'hillshade', source: 'shade', paint: { 'hillshade-exaggeration': 0.7, 'hillshade-illumination-anchor': 'map', 'hillshade-illumination-direction': 250, 'hillshade-shadow-color': '#5E4A22', 'hillshade-highlight-color': '#FFF6DD', 'hillshade-accent-color': '#D9A441' } },
      // Fields: a flat tint from afar, then edges and a paddy grid once individual plots are legible (z13 and z14).
      { id: 'farm', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: FARM, paint: { 'fill-color': C.farm, 'fill-opacity': 0.7 } },
      { id: 'farm-grid', type: 'fill', source: 'base', 'source-layer': 'landuse', minzoom: 14, filter: FARM, paint: { 'fill-pattern': FARM_PATTERN, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 15, 0.9] } },
      { id: 'farm-edge', type: 'line', source: 'base', 'source-layer': 'landuse', minzoom: 13, filter: FARM, paint: { 'line-color': '#9DB04E', 'line-opacity': 0.8, 'line-width': width(0.15, 2) } },
      { id: 'town', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('residential', 'commercial', 'industrial', 'school', 'college', 'university'), paint: { 'fill-color': C.town, 'fill-opacity': 0.7 } },
      { id: 'park', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('park', 'nature_reserve', 'grass', 'garden'), paint: { 'fill-color': C.park, 'fill-opacity': 0.8 } },
      { id: 'forest', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('wood', 'forest'), paint: { 'fill-color': C.forest, 'fill-opacity': 0.3 } },
      // Real canopy and paddies from afar. Gone by z15.5: past that its 10 m pixels just blur the vector detail.
      { id: 'imagery', type: 'raster', source: 'imagery', paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0.3, 11.5, 0.6, 13, 0.75, 14.5, 0.4, 15.5, 0], 'raster-saturation': 0.25, 'raster-brightness-min': 0.14 } },
      { id: 'water', type: 'fill', source: 'base', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': C.lake } },
      { id: 'rivers', type: 'line', source: 'base', 'source-layer': 'water', filter: kind('river', 'stream'), paint: { 'line-color': C.lake, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.8, 15, 3] } },
      { id: 'paths', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 15, filter: kind('path'), paint: { 'line-color': '#C9B48C', 'line-width': width(0.2, 4), 'line-dasharray': [2, 1] } },
      { id: 'roads-minor-case', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 13, filter: kind('minor_road'), layout: ROUND, paint: { 'line-color': '#D9CFB8', 'line-width': width(0.6, 22) } },
      // Province scale: only highways from afar, ordinary major roads from z11 (hundreds of km of them would be a red mesh).
      { id: 'roads-highway-case', type: 'line', source: 'base', 'source-layer': 'roads', filter: kind('highway'), layout: ROUND, paint: { 'line-color': '#B9575A', 'line-width': width(1.6, 40) } },
      { id: 'roads-major-case', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 11, filter: kind('major_road'), layout: ROUND, paint: { 'line-color': '#B9575A', 'line-width': width(1.6, 40) } },
      { id: 'roads-minor', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 13, filter: kind('minor_road'), layout: ROUND, paint: { 'line-color': '#FFFDF7', 'line-width': width(0.3, 18) } },
      { id: 'roads-highway', type: 'line', source: 'base', 'source-layer': 'roads', filter: kind('highway'), layout: ROUND, paint: { 'line-color': C.road, 'line-width': width(1, 34) } },
      { id: 'roads-major', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 11, filter: kind('major_road'), layout: ROUND, paint: { 'line-color': C.road, 'line-width': width(1, 34) } },
      // Street detail from z16: pale kerbs either side of major roads and a dashed centre line.
      { id: 'roads-major-kerb', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 16, filter: kind('major_road', 'highway'), layout: ROUND, paint: { 'line-color': '#F4EDE1', 'line-width': width(0.1, 3), 'line-gap-width': width(1, 34) } },
      { id: 'roads-major-centre', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 16, filter: kind('major_road', 'highway'), paint: { 'line-color': '#FFFBF0', 'line-width': width(0.05, 1.5), 'line-dasharray': [6, 6] } },
      // Dusk and night: a blue wash over the ground; extrusions and trees darken through their own lights.
      { id: 'night', type: 'fill', source: 'night', paint: { 'fill-color': '#0B1A3A', 'fill-opacity': 0, 'fill-opacity-transition': NOW } },
      // Grounding: a translucent copy pushed away from the sun per height band (cast shadow) and a blurred dark rim (contact occlusion).
      ...SHADOW_BUCKETS.map(([id, filter]) => ({ id, type: 'fill', source: 'base', 'source-layer': 'buildings', minzoom: 14, filter: ['all', BUILDING, filter], paint: { 'fill-color': '#2E2A3A', 'fill-opacity': 0, 'fill-opacity-transition': NOW, 'fill-translate-anchor': 'map', 'fill-translate-transition': NOW } })),
      { id: 'building-ao', type: 'line', source: 'base', 'source-layer': 'buildings', minzoom: 14, filter: BUILDING, paint: { 'line-color': '#3A3220', 'line-opacity': 0.5, 'line-width': width(0.25, 14), 'line-blur': width(0.25, 14) } },
      // Plaster walls with a thin roof cap in muted local roof colours (terracotta, galvanised, painted metal).
      // Colour varies by feature id only, like a painted model; it encodes no attribute.
      { id: 'buildings', type: 'fill-extrusion', source: 'base', 'source-layer': 'buildings', minzoom: 14, filter: BUILDING, paint: { 'fill-extrusion-color': ['match', ['%', ['to-number', ['id'], 0], 3], 0, '#F7F3EA', 1, '#EFE9DC', '#F3EDE3'], 'fill-extrusion-height': ['-', HEIGHT, 0.01] } },
      { id: 'roofs', type: 'fill-extrusion', source: 'base', 'source-layer': 'buildings', minzoom: 14, filter: BUILDING, paint: { 'fill-extrusion-color': ['match', ['%', ['to-number', ['id'], 0], 7], 0, '#C98A6E', 1, '#D59C7E', 2, '#B9C0C6', 3, '#93A9C0', 4, '#CDD1D3', 5, '#A9B89A', '#D8CDBD'], 'fill-extrusion-base': ['-', HEIGHT, ROOF_M], 'fill-extrusion-height': HEIGHT } },
    ],
  }
}
