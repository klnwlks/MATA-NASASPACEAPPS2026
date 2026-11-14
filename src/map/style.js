export const SCHEMATIC_HEIGHT_M = 6
export const TERRAIN_EXAGGERATION = 1.4
export const HOME_VIEW = { bearing: 180, pitch: 62 }

const C = { land: '#F2EFE0', lake: '#5C95F2', park: '#8ED9AF', forest: '#3E9B5A', road: '#E8807F', farm: '#DCE7A6', town: '#EFE4CF' }
const kind = (...k) => ['in', ['get', 'kind'], ['literal', k]]
// Base-2 growth keeps a road's on-screen width proportional to the ground it covers.
const width = (z12, z18) => ['interpolate', ['exponential', 2], ['zoom'], 12, z12, 18, z18]
const ROUND = { 'line-cap': 'round', 'line-join': 'round' }

const dem = (root) => ({ type: 'raster-dem', encoding: 'terrarium', tileSize: 256, minzoom: 8, maxzoom: 12, tiles: [`${root}data/terrain/{z}/{x}/{y}.png`], bounds: [121.091, 14.03, 121.347, 14.278] })

// Everything is served from this origin: no keys, no third-party runtime calls.
export function buildStyle(origin) {
  const root = `${origin}${import.meta.env.BASE_URL}`
  return {
    version: 8,
    glyphs: `${root}fonts/{fontstack}/{range}.pbf`,
    sources: {
      base: { type: 'vector', url: `pmtiles://${root}data/losbanos.pmtiles` },
      dem: dem(root),
      shade: dem(root), // MapLibre advises a separate source for hillshade and terrain
    },
    terrain: { source: 'dem', exaggeration: TERRAIN_EXAGGERATION },
    light: { anchor: 'map', color: '#FFE9C7', intensity: 0.45, position: [1.4, 250, 35] },
    // Warm haze toward the horizon so steep pitches read as a landscape, not a cut-off sheet.
    sky: { 'sky-color': '#9CC7EA', 'horizon-color': '#F5E6C8', 'fog-color': '#EFE8D6', 'sky-horizon-blend': 0.6, 'horizon-fog-blend': 0.7, 'fog-ground-blend': 0.35, 'atmosphere-blend': 0 },
    layers: [
      { id: 'land', type: 'background', paint: { 'background-color': C.land } },
      { id: 'relief', type: 'color-relief', source: 'shade', paint: { 'color-relief-color': ['interpolate', ['linear'], ['elevation'], 0, '#F2EFE0', 15, '#E9ECC6', 60, '#CFE29B', 200, '#9FD184', 450, '#66B86A', 800, '#3E9B5A', 1100, '#2B7D49'] } },
      { id: 'hillshade', type: 'hillshade', source: 'shade', paint: { 'hillshade-exaggeration': 0.7, 'hillshade-illumination-direction': 250, 'hillshade-shadow-color': '#5E4A22', 'hillshade-highlight-color': '#FFF6DD', 'hillshade-accent-color': '#D9A441' } },
      { id: 'farm', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('farmland', 'farmyard', 'orchard'), paint: { 'fill-color': C.farm, 'fill-opacity': 0.55 } },
      { id: 'town', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('residential', 'commercial', 'industrial', 'school', 'college', 'university'), paint: { 'fill-color': C.town, 'fill-opacity': 0.7 } },
      { id: 'park', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('park', 'nature_reserve', 'grass', 'garden'), paint: { 'fill-color': C.park, 'fill-opacity': 0.8 } },
      { id: 'forest', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('wood', 'forest'), paint: { 'fill-color': C.forest, 'fill-opacity': 0.3 } },
      { id: 'water', type: 'fill', source: 'base', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': C.lake } },
      { id: 'rivers', type: 'line', source: 'base', 'source-layer': 'water', filter: kind('river', 'stream'), paint: { 'line-color': C.lake, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.8, 15, 3] } },
      { id: 'paths', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 15, filter: kind('path'), paint: { 'line-color': '#C9B48C', 'line-width': width(0.2, 4), 'line-dasharray': [2, 1] } },
      { id: 'roads-minor-case', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 13, filter: kind('minor_road'), layout: ROUND, paint: { 'line-color': '#D9CFB8', 'line-width': width(0.6, 22) } },
      { id: 'roads-major-case', type: 'line', source: 'base', 'source-layer': 'roads', filter: kind('major_road', 'highway'), layout: ROUND, paint: { 'line-color': '#B9575A', 'line-width': width(1.6, 40) } },
      { id: 'roads-minor', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 13, filter: kind('minor_road'), layout: ROUND, paint: { 'line-color': '#FFFDF7', 'line-width': width(0.3, 18) } },
      { id: 'roads-major', type: 'line', source: 'base', 'source-layer': 'roads', filter: kind('major_road', 'highway'), layout: ROUND, paint: { 'line-color': C.road, 'line-width': width(1, 34) } },
      // Tone varies by feature id only, like a painted model; it encodes no attribute.
      { id: 'buildings', type: 'fill-extrusion', source: 'base', 'source-layer': 'buildings', minzoom: 14, filter: ['==', ['get', 'kind'], 'building'], paint: { 'fill-extrusion-color': ['match', ['%', ['to-number', ['id'], 0], 5], 0, '#F4EDE1', 1, '#EADFCB', 2, '#E9D3C0', 3, '#DCD6CB', '#F1E2C6'], 'fill-extrusion-height': ['coalesce', ['get', 'height'], SCHEMATIC_HEIGHT_M], 'fill-extrusion-opacity': 0.97, 'fill-extrusion-vertical-gradient': true } },
    ],
  }
}
