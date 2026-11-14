import { useEffect, useRef } from 'react'
import { Map, Marker, addProtocol, removeProtocol } from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'
import { buildStyle, HOME_VIEW, SHADOW_BUCKETS } from './style.js'
import { addBoundaryLayers, setSelection } from './boundaries.js'
import { addTreeLayer } from './trees.js'
import { applySun } from './sun.js'

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const padding = () =>
  window.matchMedia('(min-width: 768px)').matches
    ? { top: 96, bottom: 120, left: 56, right: 400 }
    : { top: 88, bottom: 150, left: 16, right: 16 }
const dur = (ms) => (reduceMotion() ? 0 : ms)

export default function MapStage({ barangays, selectedId, show, fit, homeTick, time, onSelect, onMunicipality, onStatus, onMap }) {
  const el = useRef(null)
  const mapRef = useRef(null)
  const live = useRef({})
  useEffect(() => {
    live.current = { onSelect, onMunicipality, onStatus, barangays, time }
  })

  useEffect(() => {
    const protocol = new Protocol()
    addProtocol('pmtiles', protocol.tile)
    let map
    try {
      map = new Map({
        container: el.current,
        style: buildStyle(window.location.origin),
        center: [121.25, 14.14],
        zoom: 11,
        ...HOME_VIEW,
        maxPitch: 80,
        attributionControl: false,
        canvasContextAttributes: { antialias: true },
      })
    } catch {
      removeProtocol('pmtiles')
      live.current.onStatus('webgl', 'failed')
      return
    }
    mapRef.current = map
    const failed = new Set()
    const fail = (key) => {
      failed.add(key)
      live.current.onStatus(key, 'failed')
    }
    map.on('error', (e) => {
      if (import.meta.env.DEV) console.warn('map error', e.sourceId, e.error?.message)
      if (e.sourceId === 'dem' || e.sourceId === 'shade') {
        map.setTerrain(null)
        fail('terrain')
      } else if (e.sourceId === 'base') fail('basemap')
      else if (e.sourceId === 'imagery') imagery.errored = true
    })
    // Single imagery tiles can fail and fall back to parents; only an imagery source that never delivers counts as down.
    const imagery = { loaded: false, errored: false }
    map.on('sourcedata', (e) => {
      if (e.sourceId === 'imagery' && e.tile) imagery.loaded = true
    })
    map.once('idle', () => {
      for (const key of ['terrain', 'basemap']) if (!failed.has(key)) live.current.onStatus(key, 'ok')
      if (imagery.errored && !imagery.loaded) {
        map.setLayoutProperty('imagery', 'visibility', 'none')
        fail('imagery')
      }
    })
    map.on('load', () => {
      onMap(map)
      applySun(map, live.current.time)
      addTreeLayer(map, `${window.location.origin}${import.meta.env.BASE_URL}data/trees.geojson`, 'buildings').catch((e) => console.error(e))
    })
    return () => {
      onMap(null)
      mapRef.current = null
      map.remove()
      removeProtocol('pmtiles')
    }
  }, [onMap])

  // Boundaries arrive independently of the basemap.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !barangays) return
    const add = () => {
      addBoundaryLayers(map, barangays.geojson, (id) => live.current.onSelect(id))
      map.fitBounds(barangays.bounds, { ...HOME_VIEW, padding: padding(), duration: 0 })
      for (const m of barangays.municipalities) {
        const pin = document.createElement('button')
        pin.type = 'button'
        pin.setAttribute('aria-label', `${m.name} storm events`)
        pin.className = 'grid size-9 place-items-center rounded-full border-2 border-white bg-cobalt text-white shadow-float hover:bg-cobalt-ink'
        pin.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>'
        // Keep the map from turning pin presses into a barangay click underneath.
        for (const type of ['mousedown', 'mouseup', 'touchstart', 'touchend', 'dblclick']) pin.addEventListener(type, (e) => e.stopPropagation())
        pin.addEventListener('click', (e) => {
          e.stopPropagation()
          live.current.onMunicipality(m)
        })
        new Marker({ element: pin }).setLngLat(m.center).addTo(map)
      }
    }
    if (map.loaded()) add()
    else map.once('load', add)
  }, [barangays])

  useEffect(() => setSelection(mapRef.current, selectedId), [selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!map?.isStyleLoaded()) return
    const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
    for (const id of ['buildings', 'roofs', 'building-ao', ...SHADOW_BUCKETS.map(([id]) => id)]) vis(id, show.buildings)
    vis('bgy-line', show.boundaries)
    vis('bgy-label', show.boundaries)
  }, [show, barangays])

  useEffect(() => {
    const map = mapRef.current
    if (map?.isStyleLoaded()) applySun(map, time)
  }, [time])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !fit) return
    map.fitBounds(fit.bounds, { padding: padding(), maxZoom: 15, bearing: map.getBearing(), pitch: map.getPitch(), duration: dur(900) })
  }, [fit])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !homeTick || !live.current.barangays) return
    map.fitBounds(live.current.barangays.bounds, { ...HOME_VIEW, padding: padding(), duration: dur(1200) })
  }, [homeTick])

  return (
    <div className="absolute inset-0">
      <div ref={el} className="h-full w-full" role="region" aria-label="Map of Bay, Laguna" />
    </div>
  )
}
