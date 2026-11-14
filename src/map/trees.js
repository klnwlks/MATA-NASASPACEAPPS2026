// Low-poly trees as fill-extrusions: mapped OSM trees get a trunk and a full-colour crown;
// decorative fill (scripts/trees.py, k=0) is drawn paler and trunkless so it reads as schematic.
const M_PER_DEG = 111320

function ring(lon, lat, r, sides) {
  const ky = r / M_PER_DEG
  const kx = ky / Math.cos((lat * Math.PI) / 180)
  const c = []
  for (let i = 0; i <= sides; i++) {
    const a = (i / sides) * 2 * Math.PI
    c.push([lon + Math.cos(a) * kx, lat + Math.sin(a) * ky])
  }
  return { type: 'Polygon', coordinates: [c] }
}

// Stable per-tree size from its coordinates, so trees don't change between loads.
const scale = (lon, lat) => 0.75 + (Math.abs(Math.sin(lon * 12.9898e4 + lat * 78.233e4)) % 1) * 0.5

function toPolygons(points, withTrunk, spread) {
  const trunks = []
  const crowns = []
  for (const [lon, lat] of points) {
    const s = scale(lon, lat)
    if (withTrunk) trunks.push({ type: 'Feature', properties: { h: 3 * s }, geometry: ring(lon, lat, 0.5 * s, 5) })
    crowns.push({ type: 'Feature', properties: { b: 2.2 * s, h: 9 * s, s }, geometry: ring(lon, lat, 2.6 * s * spread, 7) })
  }
  return { trunks, crowns }
}

const fc = (features) => ({ type: 'FeatureCollection', features })

export async function addTreeLayers(map, url, beforeId) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`trees: HTTP ${res.status}`)
  const { features } = await res.json()
  const pts = (k) => features.find((f) => f.properties.k === k)?.geometry.coordinates ?? []
  const osm = toPolygons(pts(1), true, 1)
  const fill = toPolygons(pts(0), false, 1.5) // fewer, wider crowns: sparse points still read as canopy
  if (!map.getStyle()) return // map removed while loading
  map.addSource('trees-osm-trunk', { type: 'geojson', data: fc(osm.trunks) })
  map.addSource('trees-osm-crown', { type: 'geojson', data: fc(osm.crowns) })
  map.addSource('trees-fill', { type: 'geojson', data: fc(fill.crowns) })
  const extrude = (id, source, paint) => map.addLayer({ id, type: 'fill-extrusion', source, minzoom: 14, paint: { 'fill-extrusion-vertical-gradient': true, ...paint } }, beforeId)
  extrude('trees-fill', 'trees-fill', { 'fill-extrusion-color': '#A9CE95', 'fill-extrusion-opacity': 0.85, 'fill-extrusion-base': ['get', 'b'], 'fill-extrusion-height': ['get', 'h'] })
  extrude('trees-osm-trunk', 'trees-osm-trunk', { 'fill-extrusion-color': '#7A5A3A', 'fill-extrusion-height': ['get', 'h'] })
  extrude('trees-osm-crown', 'trees-osm-crown', { 'fill-extrusion-color': ['interpolate', ['linear'], ['get', 's'], 0.75, '#3F8A48', 1.25, '#5FAE57'], 'fill-extrusion-base': ['get', 'b'], 'fill-extrusion-height': ['get', 'h'] })
}
