import { bbox } from './map/geo.js'

export const DATA_VERSION = { source: 'COD-AB v03', validOn: '2025-02-13' }

const root = import.meta.env.BASE_URL
const FLOODS = `${root}data/floods/`

// Province boundaries: 682 barangays with their municipality, and 30 municipality outlines (scripts/municipalities.py)
// that carry the pin and label position of each municipality.
export async function loadBarangays() {
  const [res, mres] = await Promise.all([fetch(`${root}data/barangays.geojson`), fetch(`${root}data/municipalities.geojson`)])
  if (!res.ok) throw new Error(`barangays ${res.status}`)
  if (!mres.ok) throw new Error(`municipalities ${mres.status}`)
  const [geojson, outlines] = await Promise.all([res.json(), mres.json()])
  const list = geojson.features
    .map((f) => ({
      psgc: f.properties.psgc,
      name: f.properties.name,
      municipality: f.properties.muni,
      munipsgc: f.properties.munipsgc,
      bounds: bbox(f.geometry),
    }))
    .sort((a, b) => a.name.localeCompare(b.name))
  const all = { type: 'GeometryCollection', geometries: geojson.features.map((f) => f.geometry) }
  const municipalities = outlines.features
    .map((f) => ({ psgc: f.properties.munipsgc, name: f.properties.name, bounds: bbox(f.geometry), center: f.properties.center }))
    .sort((a, b) => a.name.localeCompare(b.name))
  return { geojson, outlines, list, municipalities, bounds: bbox(all) }
}

// Province overview of the replay (scripts/flood_summary.py): the frames every municipality shares, and one string per
// barangay with one character per frame: 1 flooded, 0 none seen, - unknown. The lake series (scripts/lake_level.py) is
// context only: if it is missing the replay still works without it.
export async function loadFloods() {
  const get = (file) => fetch(`${FLOODS}${file}`)
  const [index, lake] = await Promise.all([get('index.json'), get('lake.json').catch(() => null)])
  if (!index.ok) throw new Error(`floods index ${index.status}`)
  const m = await index.json()
  const states = await get(m.statesFile ?? 'states.json')
  if (!states.ok) throw new Error(`floods states ${states.status}`)
  return { ...m, states: await states.json(), lake: lake?.ok ? await lake.json() : null }
}

// One municipality's barangay records and image URLs. Loaded when it is first opened. Its frames line up with the shared
// frames by pass time; a frame without an image in this municipality has no url and draws nothing.
export async function loadMunicipality(floods, psgc) {
  const entry = floods.municipalities[psgc]
  const res = await fetch(`${FLOODS}${entry?.manifest ?? `${psgc}/manifest.json`}`)
  if (!res.ok) throw new Error(`manifest ${psgc} ${res.status}`)
  const m = await res.json()
  const own = new Map((m.frames ?? []).map((f) => [f.utc, f]))
  const url = (file) => file && `${FLOODS}${file}`
  const n = floods.frames.length
  for (const [id, rec] of Object.entries(m.barangays)) if (rec.state.length !== n) throw new Error(`manifest ${psgc}: ${id} has ${rec.state.length} frames, expected ${n}`)
  return { ...m, frames: floods.frames.map((f) => ({ url: url(own.get(f.utc)?.file), coherenceUrl: url(own.get(f.utc)?.coherenceFile), nisarUrl: url(own.get(f.utc)?.nisarFile) })) }
}

// Observed state at one frame from states.json: 1 flooded, 0 none seen, -1 unknown or no record.
export const stateAt = (states, psgc, frame) => ({ 1: 1, 0: 0 })[states?.[psgc]?.[frame]] ?? -1

const PHT = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const DAY = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', day: 'numeric', month: 'short', year: 'numeric' })
export const phtTime = (utc) => PHT.format(new Date(utc))
export const shortDate = (utc) => DAY.format(new Date(utc))
