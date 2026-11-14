const COBALT = '#1F4FD8'
const SRC = 'barangays'
const none = ['==', ['get', 'psgc'], '']

// Registered once per map. The fill is a near-transparent hit target so the whole
// polygon is selectable, including where buildings stand on it.
export function addBoundaryLayers(map, geojson, onSelect) {
  if (map.getSource(SRC)) return
  map.addSource(SRC, { type: 'geojson', data: geojson, promoteId: 'psgc' })
  const line = { 'line-join': 'round', 'line-cap': 'round' }
  map.addLayer({ id: 'bgy-fill', type: 'fill', source: SRC, paint: { 'fill-color': COBALT, 'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.12, 0.01] } })
  map.addLayer({ id: 'bgy-line', type: 'line', source: SRC, layout: line, paint: { 'line-color': COBALT, 'line-width': 1.5, 'line-opacity': 0.85 } })
  map.addLayer({ id: 'bgy-sel-fill', type: 'fill', source: SRC, filter: none, paint: { 'fill-color': COBALT, 'fill-opacity': 0.25 } })
  map.addLayer({ id: 'bgy-sel-casing', type: 'line', source: SRC, filter: none, layout: line, paint: { 'line-color': '#FFFFFF', 'line-width': 11 } })
  map.addLayer({ id: 'bgy-sel-line', type: 'line', source: SRC, filter: none, layout: line, paint: { 'line-color': COBALT, 'line-width': 5 } })
  map.addLayer({
    id: 'bgy-label',
    type: 'symbol',
    source: SRC,
    layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Medium'], 'text-size': ['interpolate', ['linear'], ['zoom'], 10, 11, 14, 14], 'text-max-width': 7, 'text-pitch-alignment': 'viewport' },
    paint: { 'text-color': '#0F1B33', 'text-halo-color': '#FBFAF6', 'text-halo-width': 2 },
  })

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

export function setSelection(map, id) {
  if (!map?.getLayer('bgy-sel-fill')) return
  const f = id ? ['==', ['get', 'psgc'], id] : none
  for (const layer of ['bgy-sel-fill', 'bgy-sel-casing', 'bgy-sel-line']) map.setFilter(layer, f)
}
