import { bbox } from './map/geo.js'

export const DATA_VERSION = { source: 'COD-AB v03', validOn: '2025-02-13' }

export async function loadBarangays() {
  const res = await fetch(`${import.meta.env.BASE_URL}data/barangays.geojson`)
  if (!res.ok) throw new Error(`barangays ${res.status}`)
  const geojson = await res.json()
  const list = geojson.features
    .map((f) => ({
      psgc: f.properties.psgc,
      name: f.properties.name,
      municipality: f.properties.muni,
      bounds: bbox(f.geometry),
    }))
    .sort((a, b) => a.name.localeCompare(b.name))
  const all = { type: 'GeometryCollection', geometries: geojson.features.map((f) => f.geometry) }
  return { geojson, list, bounds: bbox(all) }
}
