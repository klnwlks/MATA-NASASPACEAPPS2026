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
  // One pin per municipality, at the center of its barangays' combined extent.
  const munis = new Map()
  for (const b of list) {
    const m = munis.get(b.municipality) ?? { name: b.municipality, bounds: b.bounds }
    m.bounds = [[Math.min(m.bounds[0][0], b.bounds[0][0]), Math.min(m.bounds[0][1], b.bounds[0][1])], [Math.max(m.bounds[1][0], b.bounds[1][0]), Math.max(m.bounds[1][1], b.bounds[1][1])]]
    munis.set(b.municipality, m)
  }
  const municipalities = [...munis.values()].map((m) => ({ ...m, center: [(m.bounds[0][0] + m.bounds[1][0]) / 2, (m.bounds[0][1] + m.bounds[1][1]) / 2] }))
  return { geojson, list, municipalities, bounds: bbox(all) }
}

// Observed Sentinel-1 frames and per-barangay flood records, precomputed by scripts/floods.py and flood_summary.py.
export async function loadFloods() {
  const res = await fetch(`${import.meta.env.BASE_URL}data/floods/manifest.json`)
  if (!res.ok) throw new Error(`floods ${res.status}`)
  const m = await res.json()
  return { ...m, frames: m.frames.map((f) => ({ ...f, url: `${import.meta.env.BASE_URL}data/floods/${f.file}` })) }
}

const PHT = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const DAY = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', day: 'numeric', month: 'short', year: 'numeric' })
export const phtTime = (utc) => PHT.format(new Date(utc))
export const shortDate = (utc) => DAY.format(new Date(utc))
