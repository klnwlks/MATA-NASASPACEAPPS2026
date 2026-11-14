import { useEffect, useRef } from 'react'
import { Map, addProtocol, removeProtocol } from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'
import { buildStyle, HOME_VIEW } from './style.js'
import { addBoundaryLayers, setSelection } from './boundaries.js'

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const padding = () =>
  window.matchMedia('(min-width: 768px)').matches
    ? { top: 96, bottom: 120, left: 56, right: 400 }
    : { top: 88, bottom: 150, left: 16, right: 16 }
const dur = (ms) => (reduceMotion() ? 0 : ms)

export default function MapStage({ barangays, selectedId, show, fit, homeTick, onSelect, onStatus, onMap }) {
  const el = useRef(null)
  const mapRef = useRef(null)
  const live = useRef({})
  useEffect(() => {
    live.current = { onSelect, onStatus, barangays }
  })

  useEffect(() => {
    const protocol = new Protocol()
    addProtocol('pmtiles', protocol.tile)
    let map
    try {
      map = new Map({
        container: el.current,
        style: buildStyle(window.location.origin),
        center: [121.22, 14.17],
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
    })
    map.once('idle', () => {
      for (const key of ['terrain', 'basemap']) if (!failed.has(key)) live.current.onStatus(key, 'ok')
    })
    map.on('load', () => onMap(map))
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
    }
    if (map.loaded()) add()
    else map.once('load', add)
  }, [barangays])

  useEffect(() => setSelection(mapRef.current, selectedId), [selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!map?.isStyleLoaded()) return
    const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
    vis('buildings', show.buildings)
    vis('bgy-line', show.boundaries)
    vis('bgy-label', show.boundaries)
  }, [show, barangays])

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
      <div ref={el} className="h-full w-full" role="region" aria-label="Map of Los Baños, Laguna" />
    </div>
  )
}
