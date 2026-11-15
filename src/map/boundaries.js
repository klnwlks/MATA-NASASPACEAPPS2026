const COBALT = '#FFF700'
const COBALT_INK = '#CFC82D'
const SRC = 'barangays'
const MUNI = 'municipalities'
const PINS = 'municipality-points'
const DATA_RED = '#D92D20'
const none = ['==', ['get', 'psgc'], '']
export const BOUNDARY_LAYERS = ['bgy-line', 'bgy-label', 'muni-line', 'muni-data-fill', 'muni-data-line', 'muni-label']
export const LABEL_ZOOM = 11.5 // barangay names from here; below it the municipality names are drawn
export const PIN_ZOOM = 12.5 // municipality pins and names give way to the barangays from here

// Hatching for unknown: a shape cue, so the state never depends on colour alone. Tiles seamlessly on a 16 px cell.
function hatch() {
  const c = document.createElement('canvas')
  c.width = c.height = 16
  const g = c.getContext('2d')
  g.strokeStyle = '#56607A'
  g.lineWidth = 1.2
  g.lineCap = 'square'
  g.beginPath()
  for (const o of [-16, 0, 16]) {
    g.moveTo(o, 16)
    g.lineTo(o + 16, 0)
  }
  g.stroke()
  return g.getImageData(0, 0, 16, 16)
}

// One character of the barangay's state string for this frame: 1 flooded, 0 none seen, anything else unknown.
const at = (frame) => ['slice', ['get', 'st'], frame, frame + 1]
// Fills fade as the 3D water and the real ground take over at municipality zoom.
const fade = (value, near, far) => ['interpolate', ['linear'], ['zoom'], 10, value(near), 13, value(far)]

// Registered once per map. The fill is a near-transparent hit target so the whole
// polygon is selectable, including where buildings stand on it.
export function addBoundaryLayers(map, { geojson, outlines, municipalities }, onSelect) {
  if (map.getSource(SRC)) return
  map.addSource(SRC, { type: 'geojson', data: geojson, promoteId: 'psgc' })
  map.addSource(MUNI, { type: 'geojson', data: outlines })
  map.addSource(PINS, { type: 'geojson', data: { type: 'FeatureCollection', features: municipalities.map((m) => ({ type: 'Feature', properties: { name: m.name }, geometry: { type: 'Point', coordinates: m.center } })) } })
  map.addImage('unknown-hatch', hatch(), { pixelRatio: 2 })
  const line = { 'line-join': 'round', 'line-cap': 'round' }
  const hidden = { visibility: 'none' } // the state layers wait for states.json: nothing is drawn as dry or unknown before it arrives
  map.addLayer({ id: 'bgy-fill', type: 'fill', source: SRC, paint: { 'fill-color': COBALT, 'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.12, 0.01] } })
  map.addLayer({ id: 'bgy-flood', type: 'fill', source: SRC, layout: hidden, paint: { 'fill-color': COBALT, 'fill-opacity': 0 } })
  map.addLayer({ id: 'bgy-unknown', type: 'fill', source: SRC, layout: hidden, paint: { 'fill-pattern': 'unknown-hatch', 'fill-opacity': 0 } })
  map.addLayer({ id: 'bgy-line', type: 'line', source: SRC, layout: line, paint: { 'line-color': COBALT, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.3, 12, 1, 14, 1.5], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0.45, 13, 0.85] } })
  map.addLayer({ id: 'muni-line', type: 'line', source: MUNI, layout: line, paint: { 'line-color': COBALT_INK, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 1.4, 12, 2.2], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.9, 14, 0.4] } })
  map.addLayer({ id: 'muni-data-fill', type: 'fill', source: MUNI, filter: none, paint: { 'fill-color': DATA_RED, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 10, 0.1, 13, 0] } })
  map.addLayer({ id: 'muni-data-line', type: 'line', source: MUNI, filter: none, layout: line, paint: { 'line-color': DATA_RED, 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2, 12, 3.2], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 1, 14, 0.5] } })
  map.addLayer({ id: 'muni-sel-fill', type: 'fill', source: MUNI, filter: none, paint: { 'fill-color': COBALT, 'fill-opacity': 0.2 } })
  map.addLayer({ id: 'muni-sel-casing', type: 'line', source: MUNI, filter: none, layout: line, paint: { 'line-color': '#FFFFFF', 'line-width': 7 } })
  map.addLayer({ id: 'muni-sel-line', type: 'line', source: MUNI, filter: none, layout: line, paint: { 'line-color': COBALT_INK, 'line-width': 4 } })
  map.addLayer({ id: 'bgy-sel-fill', type: 'fill', source: SRC, filter: none, paint: { 'fill-color': COBALT, 'fill-opacity': 0.25 } })
  map.addLayer({ id: 'bgy-sel-casing', type: 'line', source: SRC, filter: none, layout: line, paint: { 'line-color': '#FFFFFF', 'line-width': 11 } })
  map.addLayer({ id: 'bgy-sel-line', type: 'line', source: SRC, filter: none, layout: line, paint: { 'line-color': COBALT, 'line-width': 5 } })
  const text = { 'text-font': ['Noto Sans Medium'], 'text-pitch-alignment': 'viewport' }
  const ink = { 'text-color': '#0F1B33', 'text-halo-color': '#FBFAF6', 'text-halo-width': 2 }
  map.addLayer({ id: 'bgy-label', type: 'symbol', source: SRC, minzoom: LABEL_ZOOM, layout: { ...text, 'text-field': ['get', 'name'], 'text-size': ['interpolate', ['linear'], ['zoom'], 11, 11, 14, 14], 'text-max-width': 7 }, paint: ink })
  // Under the DOM pin: the pin is 36 px, the name sits just below it.
  map.addLayer({ id: 'muni-label', type: 'symbol', source: PINS, minzoom: 8, maxzoom: PIN_ZOOM, layout: { ...text, 'text-field': ['get', 'name'], 'text-size': 13, 'text-anchor': 'top', 'text-offset': [0, 1.5], 'text-max-width': 8 }, paint: ink })

  let hover = null
  const pick = (point) => {
    const hits = map.queryRenderedFeatures(point, { layers: ['bgy-fill'] })
    // Shared edges can return two polygons; the lower PSGC wins every time.
    return hits.map((h) => h.properties.psgc).sort()[0] ?? null
  }
  map.on('mousemove', 'bgy-fill', (e) => {
    const id = pick(e.point)
    if (id === hover) return
    if (hover) map.setFeatureState({ source: SRC, id: hover }, { hover: false })
    hover = id
    if (id) map.setFeatureState({ source: SRC, id }, { hover: true })
    map.getCanvas().style.cursor = id ? 'pointer' : ''
  })
  map.on('mouseleave', 'bgy-fill', () => {
    if (hover) map.setFeatureState({ source: SRC, id: hover }, { hover: false })
    hover = null
    map.getCanvas().style.cursor = ''
  })
  map.on('click', (e) => {
    const id = pick(e.point)
    if (id) onSelect(id)
  })
}

// Joins states.json onto the polygons (property st) and reveals the state layers. Call once per states object.
export function setStates(map, geojson, states) {
  const src = map?.getSource(SRC)
  if (!src) return
  src.setData({ ...geojson, features: geojson.features.map((f) => ({ ...f, properties: { ...f.properties, st: states[f.properties.psgc] ?? '' } })) })
  for (const id of ['bgy-flood', 'bgy-unknown']) map.setLayoutProperty(id, 'visibility', 'visible')
}

// Two paint updates per frame, not one feature-state call per barangay.
export function setFrame(map, frame) {
  if (!map?.getLayer('bgy-flood')) return
  const s = at(frame)
  map.setPaintProperty('bgy-flood', 'fill-opacity', fade((v) => ['match', s, '1', v, 0], 0.55, 0.2))
  map.setPaintProperty('bgy-unknown', 'fill-opacity', fade((v) => ['match', s, '1', 0, '0', 0, v], 0.55, 0.3))
}

export function setSelection(map, id) {
  if (!map?.getLayer('bgy-sel-fill')) return
  const f = id ? ['==', ['get', 'psgc'], id] : none
  for (const layer of ['bgy-sel-fill', 'bgy-sel-casing', 'bgy-sel-line']) map.setFilter(layer, f)
}

export function setMunicipalitySelection(map, id) {
  if (!map?.getLayer('muni-sel-fill')) return
  const f = id ? ['==', ['get', 'munipsgc'], id] : none
  for (const layer of ['muni-sel-fill', 'muni-sel-casing', 'muni-sel-line']) map.setFilter(layer, f)
}

// Barangay names show only for municipalities with published flood records; the others stay unlabelled.
export function setLabelMunicipalities(map, ids) {
  if (!map?.getLayer('bgy-label')) return
  map.setFilter('bgy-label', ['in', ['get', 'munipsgc'], ['literal', ids]])
  const data = ids.length ? ['in', ['get', 'munipsgc'], ['literal', ids]] : none
  for (const layer of ['muni-data-fill', 'muni-data-line']) map.setFilter(layer, data)
}
