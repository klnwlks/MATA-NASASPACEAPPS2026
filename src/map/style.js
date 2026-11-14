export const SCHEMATIC_HEIGHT_M = 6
export const TERRAIN_EXAGGERATION = 1.4
export const HOME_VIEW = { bearing: 180, pitch: 62 }

const C = { land: '#F2EFE0', lake: '#11B5AE', park: '#8ED9AF', forest: '#3E9B5A', road: '#E8807F' }
const kind = (...k) => ['in', ['get', 'kind'], ['literal', k]]

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
    layers: [
      { id: 'land', type: 'background', paint: { 'background-color': C.land } },
      { id: 'hillshade', type: 'hillshade', source: 'shade', paint: { 'hillshade-exaggeration': 0.55, 'hillshade-illumination-direction': 250, 'hillshade-shadow-color': '#8A6A3F', 'hillshade-highlight-color': '#FFF6DD', 'hillshade-accent-color': '#B98B52' } },
      { id: 'park', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('park', 'nature_reserve', 'grass', 'garden'), paint: { 'fill-color': C.park, 'fill-opacity': 0.8 } },
      { id: 'forest', type: 'fill', source: 'base', 'source-layer': 'landuse', filter: kind('wood', 'forest'), paint: { 'fill-color': C.forest, 'fill-opacity': 0.55 } },
      { id: 'water', type: 'fill', source: 'base', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': C.lake } },
      { id: 'rivers', type: 'line', source: 'base', 'source-layer': 'water', filter: kind('river', 'stream'), paint: { 'line-color': C.lake, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.8, 15, 3] } },
      { id: 'roads-minor', type: 'line', source: 'base', 'source-layer': 'roads', minzoom: 13, filter: kind('minor_road'), paint: { 'line-color': '#FFFFFF', 'line-width': ['interpolate', ['linear'], ['zoom'], 13, 0.5, 17, 4] } },
      { id: 'roads-major', type: 'line', source: 'base', 'source-layer': 'roads', filter: kind('major_road', 'highway'), paint: { 'line-color': C.road, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 1, 17, 7] } },
      { id: 'buildings', type: 'fill-extrusion', source: 'base', 'source-layer': 'buildings', minzoom: 14, filter: ['==', ['get', 'kind'], 'building'], paint: { 'fill-extrusion-color': '#FBF8F0', 'fill-extrusion-height': ['coalesce', ['get', 'height'], SCHEMATIC_HEIGHT_M], 'fill-extrusion-opacity': 0.96, 'fill-extrusion-vertical-gradient': true } },
    ],
  }
}
