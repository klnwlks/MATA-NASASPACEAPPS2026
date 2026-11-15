import { useEffect, useRef, useState } from 'react'
import { Map, Marker, addProtocol, removeProtocol } from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'
import { buildStyle, HOME_VIEW, PROVINCE_VIEW, SHADOW_BUCKETS } from './style.js'
import { addBoundaryLayers, setFrame, setSelection, setMunicipalitySelection, setLabelMunicipalities, setStates, BOUNDARY_LAYERS, PIN_ZOOM } from './boundaries.js'
import { addTreeLayer } from './trees.js'
import { addWaterLayer, floodStage } from './water.js'
import { createSlot } from './slot.js'
import { addFarmPattern } from './farmPattern.js'
import { applySun } from './sun.js'

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const padding = () =>
  window.matchMedia('(min-width: 768px)').matches
    ? { top: 96, bottom: 120, left: 56, right: 400 }
    : { top: 88, bottom: 150, left: 16, right: 16 }
const dur = (ms) => (reduceMotion() ? 0 : ms)
// The heavy layers belong to the focused municipality and only appear once it fills a useful part of the screen.
// Each switches on at its zoom and off half a zoom level lower, so a hovering zoom does not reload it.
const WATER_ZOOM = 11
const TREES_ZOOM = 13
const gate = (on, zoom, at) => (on ? zoom >= at - 0.5 : zoom >= at)
const PIN_BASE = 'grid place-items-center rounded-full border-2 shadow-float'
function stylePin(pin, name, mapped) {
  pin.className = mapped ? `${PIN_BASE} size-10 border-white bg-cobalt text-white ring-4 ring-cobalt/30 hover:bg-cobalt-ink` : `${PIN_BASE} size-8 border-line bg-chalk text-muted hover:text-ink`
  pin.setAttribute('aria-label', mapped ? `${name}, municipality: observed flood runs` : `${name}, municipality: no observations loaded`)
}

export default function MapStage({ barangays, floods, manifest, focus, focusPsgc, frame, selectedId, selectedMunicipalityId, show, fit, homeTick, time, onSelect, onMunicipality, onCenter, onStatus, onMap }) {
  const el = useRef(null)
  const mapRef = useRef(null)
  const live = useRef({})
  const slots = useRef(null)
  const loaded = useRef(false)
  const queue = useRef([])
  const pins = useRef([])
  const [zoomed, setZoomed] = useState({ water: false, trees: false })
  useEffect(() => {
    live.current = { onSelect, onMunicipality, onCenter, onStatus, barangays, floods, time, frame, focus, selectedId, selectedMunicipalityId }
  })
  // Style-dependent work waits for the first 'load'; map.loaded() is false whenever tiles are in flight, so it cannot gate this.
  const whenLoaded = (fn) => (loaded.current ? fn() : queue.current.push(fn))

  useEffect(() => {
    const protocol = new Protocol()
    addProtocol('pmtiles', protocol.tile)
    let map
    // A 2x screen costs 4x the fragments of 1x for little visible gain under terrain, haze and 3D; 1.5x keeps text crisp.
    // MSAA only pays off at 1x: above that the extra pixels already smooth the edges.
    const pixelRatio = Math.min(window.devicePixelRatio, 1.5)
    try {
      map = new Map({
        container: el.current,
        style: buildStyle(window.location.origin),
        center: [121.32, 14.28],
        zoom: 9.4,
        ...PROVINCE_VIEW,
        maxPitch: 70, // HOME_VIEW sits at 62; steeper views pull in many far tiles for a strip of horizon
        attributionControl: false,
        pixelRatio,
        canvasContextAttributes: { antialias: pixelRatio <= 1 },
      })
    } catch {
      removeProtocol('pmtiles')
      live.current.onStatus('webgl', 'failed')
      return
    }
    mapRef.current = map
    const origin = window.location.origin + import.meta.env.BASE_URL
    slots.current = {
      water: createSlot(() => addWaterLayer(map, live.current.focus.corners, origin)),
      trees: createSlot((psgc) => addTreeLayer(map, `${origin}data/trees/${psgc}.geojson`, 'buildings')),
    }
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
      loaded.current = true
      addFarmPattern(map)
      onMap(map)
      applySun(map, live.current.time)
      for (const fn of queue.current.splice(0)) fn()
    })
    // After each move: gate the heavy layers by zoom, hide the pins once barangays take over, and tell the app which
    // municipality is under the middle of the screen so it can load that one.
    const settle = () => {
      const z = map.getZoom()
      setZoomed((s) => {
        const next = { water: gate(s.water, z, WATER_ZOOM), trees: gate(s.trees, z, TREES_ZOOM) }
        return next.water === s.water && next.trees === s.trees ? s : next
      })
      for (const pin of pins.current) pin.style.display = z < 8 || z >= PIN_ZOOM ? 'none' : ''
      if (z < WATER_ZOOM || !map.getLayer('bgy-fill')) return
      const c = map.project(map.getCenter())
      const hit = map.queryRenderedFeatures(c, { layers: ['bgy-fill'] })[0]
      if (hit) live.current.onCenter(hit.properties.munipsgc)
    }
    map.on('moveend', settle)
    return () => {
      loaded.current = false
      queue.current = []
      slots.current = null
      pins.current = []
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
    whenLoaded(() => {
      addBoundaryLayers(map, barangays, (id) => live.current.onSelect(id))
      setSelection(map, live.current.selectedId)
      setMunicipalitySelection(map, live.current.selectedMunicipalityId)
      // The province determines the widest view; the initial and reset views focus on Bay.
      const provinceView = map.cameraForBounds(barangays.bounds, { padding: 0, bearing: 0, pitch: 0 })
      if (provinceView) map.setMinZoom(provinceView.zoom)
      const bay = barangays.municipalities.find((m) => m.name.toLowerCase() === 'bay')
      map.fitBounds(bay?.bounds ?? barangays.bounds, { ...HOME_VIEW, padding: padding(), duration: 0 })
      pins.current = barangays.municipalities.map((m) => {
        const pin = document.createElement('button')
        pin.type = 'button'
        pin.style.display = map.getZoom() < 8 || map.getZoom() >= PIN_ZOOM ? 'none' : ''
        pin.dataset.psgc = m.psgc
        stylePin(pin, m.name, !!live.current.floods?.municipalities[m.psgc])
        pin.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>'
        // Keep the map from turning pin presses into a barangay click underneath.
        for (const type of ['mousedown', 'mouseup', 'touchstart', 'touchend', 'dblclick']) pin.addEventListener(type, (e) => e.stopPropagation())
        pin.addEventListener('click', (e) => {
          e.stopPropagation()
          live.current.onMunicipality(m)
        })
        new Marker({ element: pin }).setLngLat(m.center).addTo(map)
        return pin
      })
    })
  }, [barangays])

  // Pins with published flood records stand out; the rest are plain reference markers. Floods may arrive after the pins.
  useEffect(() => {
    if (!floods) return
    for (const pin of pins.current) stylePin(pin, barangays?.municipalities.find((m) => m.psgc === pin.dataset.psgc)?.name ?? '', !!floods.municipalities[pin.dataset.psgc])
  }, [floods, barangays])

  useEffect(() => {
    const map = mapRef.current
    if (map && barangays) whenLoaded(() => setLabelMunicipalities(map, Object.keys(floods?.municipalities ?? {})))
  }, [floods, barangays])

  // Observed state per barangay per frame: the polygons carry the state strings, a frame change only repaints.
  const states = floods?.states
  useEffect(() => {
    const map = mapRef.current
    if (!map || !barangays || !states) return
    whenLoaded(() => {
      setStates(map, barangays.geojson, states)
      setFrame(map, live.current.frame)
    })
  }, [barangays, states])
  useEffect(() => {
    const map = mapRef.current
    if (map) whenLoaded(() => setFrame(map, frame))
  }, [frame])

  useEffect(() => setSelection(mapRef.current, selectedId), [selectedId])
  useEffect(() => setMunicipalitySelection(mapRef.current, selectedMunicipalityId), [selectedMunicipalityId])

  // The water surface (and the coherence and NISAR overlays that ride on it) is one mesh for the focused municipality.
  // It exists only from WATER_ZOOM and only once that municipality's manifest has loaded; the slot unloads it on focus change.
  const waterKey = focus && manifest && zoomed.water ? focus.psgc : null
  useEffect(() => {
    const map = mapRef.current
    if (!map || !slots.current) return
    const slot = slots.current.water
    whenLoaded(() => {
      slot.set(waterKey).then((w) => {
        const f = manifest?.frames[frame]
        if (!w || slot.key !== waterKey) return
        w.set(f?.url, floodStage(floods.lake, floods.frames[frame].utc))
        w.overlay('coherence', f?.coherenceUrl, show.coherence)
        w.overlay('nisar', f?.nisarUrl, show.nisar)
      })
    })
  }, [waterKey, manifest, floods, frame, show])

  const treesKey = focusPsgc && zoomed.trees && show.trees ? focusPsgc : null
  useEffect(() => {
    if (slots.current) whenLoaded(() => slots.current?.trees.set(treesKey))
  }, [treesKey])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    whenLoaded(() => {
      const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
      for (const id of ['buildings', 'roofs', 'building-ao', ...SHADOW_BUCKETS.map(([id]) => id)]) vis(id, show.buildings)
      for (const id of BOUNDARY_LAYERS) vis(id, show.boundaries)
    })
  }, [show, barangays])

  useEffect(() => {
    const map = mapRef.current
    if (map?.isStyleLoaded()) applySun(map, time)
  }, [time])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !fit) return
    map.fitBounds(fit.bounds, { padding: padding(), maxZoom: 15, bearing: map.getBearing(), pitch: Math.max(map.getPitch(), HOME_VIEW.pitch), duration: dur(900) })
  }, [fit])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !homeTick || !live.current.barangays) return
    const bay = live.current.barangays.municipalities.find((m) => m.name.toLowerCase() === 'bay')
    map.fitBounds(bay?.bounds ?? live.current.barangays.bounds, { ...HOME_VIEW, padding: padding(), duration: dur(1200) })
  }, [homeTick])

  return (
    <div className="absolute inset-0">
      <div ref={el} className="h-full w-full" role="region" aria-label="Map of Laguna province" />
    </div>
  )
}
