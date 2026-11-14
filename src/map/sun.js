// Time of day: real sun position over Los Baños drives the map light, sky, hillshade, building shadows and a
// night tint. Shadows are "kinda" dynamic: direction and length follow the sun, but MapLibre can only offset a
// whole layer, so buildings are bucketed by height and each bucket gets one offset.
import { SHADOW_BUCKETS } from './style.js'

const RAD = Math.PI / 180
const LAT = 14.17
const LON = 121.24
const MANILA_UTC_OFFSET_MIN = 480 // UTC+8, no daylight saving
const METRES_PER_PX_Z0 = 75892 // 78271.5 m/px at z0 for 512 px tiles, times cos(14.17°)

// Low-precision solar ephemeris (Astronomical Almanac, about 0.01° over decades): plenty for map lighting.
export function sunPosition(date) {
  const d = date.getTime() / 86400000 - 10957.5 // days since J2000.0
  const g = (357.529 + 0.98560028 * d) * RAD
  const L = (280.459 + 0.98564736 * d + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * RAD
  const e = (23.439 - 0.00000036 * d) * RAD
  const ra = Math.atan2(Math.cos(e) * Math.sin(L), Math.cos(L))
  const dec = Math.asin(Math.sin(e) * Math.sin(L))
  const ha = ((18.697374558 + 24.06570982441908 * d) * 15 + LON) * RAD - ra
  const phi = LAT * RAD
  const altitude = Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(ha))
  const azimuth = Math.atan2(-Math.sin(ha), Math.tan(dec) * Math.cos(phi) - Math.sin(phi) * Math.cos(ha))
  return { azimuth: (azimuth / RAD + 360) % 360, altitude: altitude / RAD }
}

// Today's date at a Manila clock time, as an absolute instant.
export function manilaTime(minutes, now = new Date()) {
  const local = new Date(now.getTime() + MANILA_UTC_OFFSET_MIN * 60000)
  return new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate()) + (minutes - MANILA_UTC_OFFSET_MIN) * 60000)
}

export function manilaMinutes(now = new Date()) {
  const t = new Date(now.getTime() + MANILA_UTC_OFFSET_MIN * 60000)
  return t.getUTCHours() * 60 + t.getUTCMinutes()
}

// Keyframes by sun altitude in degrees. Between keyframes every value is interpolated.
const KEYS = [
  { alt: -12, sky: '#0B1530', horizon: '#1E2B4D', fog: '#18223D', light: '#59678F', intensity: 0.1, night: 0.6, shadow: 0, sun: 0, ambient: 0.35 },
  { alt: -3, sky: '#3D5A8C', horizon: '#E8955A', fog: '#B98F7A', light: '#B98872', intensity: 0.2, night: 0.3, shadow: 0, sun: 0.3, ambient: 0.7 },
  { alt: 6, sky: '#8DB8E0', horizon: '#FFD29A', fog: '#F2DCBC', light: '#FFD7A3', intensity: 0.45, night: 0, shadow: 0.3, sun: 1.8, ambient: 1.1 },
  { alt: 30, sky: '#9CC7EA', horizon: '#F5E6C8', fog: '#EFE8D6', light: '#FFFFFF', intensity: 0.25, night: 0, shadow: 0.26, sun: 2.2, ambient: 1.3 },
]

const hex = (s) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16))
const mix = (a, b, t) => (typeof a === 'number' ? a + (b - a) * t : `rgb(${hex(a).map((v, i) => Math.round(v + (hex(b)[i] - v) * t)).join(',')})`)

export function lighting(altitude) {
  const i = KEYS.findIndex((k) => k.alt > altitude)
  if (i === 0) return { ...KEYS[0] }
  if (i === -1) return { ...KEYS[KEYS.length - 1] }
  const [a, b] = [KEYS[i - 1], KEYS[i]]
  const t = (altitude - a.alt) / (b.alt - a.alt)
  return Object.fromEntries(Object.keys(a).map((k) => [k, mix(a[k], b[k], t)]))
}

// Ground offset in pixels at zoom z for a shadow of `metres`, pointing away from the sun (x east, y south).
function shadowTranslate(metres, azimuth) {
  const [dx, dy] = [-Math.sin(azimuth * RAD) * metres, Math.cos(azimuth * RAD) * metres]
  const at = (z) => ['literal', [(dx * 2 ** z) / METRES_PER_PX_Z0, (dy * 2 ** z) / METRES_PER_PX_Z0]]
  return ['interpolate', ['exponential', 2], ['zoom'], 12, at(12), 20, at(20)]
}

export function applySun(map, date) {
  const sun = sunPosition(date)
  const p = lighting(sun.altitude)
  map.setSky({ 'sky-color': p.sky, 'horizon-color': p.horizon, 'fog-color': p.fog, 'sky-horizon-blend': 0.6, 'horizon-fog-blend': 0.7, 'fog-ground-blend': 0.35, 'atmosphere-blend': 0 })
  map.setLight({ anchor: 'map', color: p.light, intensity: p.intensity, position: [1.2, sun.azimuth, Math.min(85, Math.max(0, 90 - sun.altitude))] })
  map.setPaintProperty('hillshade', 'hillshade-illumination-direction', sun.azimuth)
  map.setPaintProperty('night', 'fill-opacity', p.night)
  // Shadow length h / tan(altitude), capped so a low sun doesn't smear shadows across whole blocks.
  const stretch = Math.min(4, 1 / Math.tan(Math.max(sun.altitude, 1) * RAD))
  for (const [id, , h] of SHADOW_BUCKETS) {
    map.setPaintProperty(id, 'fill-translate', shadowTranslate(h * stretch, sun.azimuth))
    map.setPaintProperty(id, 'fill-opacity', p.shadow)
  }
  // MapLibre caches draped layers per terrain tile and re-renders them only when a source changes, not on paint
  // changes. A feature-state change on the night source counts as a source change. It must land after the frame
  // that applies the new paint values, or the cache is rebuilt with the old ones.
  map.once('render', () => map.setFeatureState({ source: 'night', id: 1 }, { at: date.getTime() }))
  map.triggerRepaint()
  return { ...sun, ...p }
}
