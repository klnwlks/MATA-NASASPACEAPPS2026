import { useEffect, useState } from 'react'

const btn = 'rounded-lg border border-line bg-chalk px-3 py-1.5 text-sm font-medium hover:bg-cobalt-tint'

function Toggle({ on, onChange, children }) {
  return (
    <button type="button" aria-pressed={on} onClick={() => onChange(!on)} className={`${btn} text-left ${on ? 'border-cobalt bg-cobalt-tint text-cobalt-ink' : ''}`}>
      {children}
    </button>
  )
}

export default function MapControls({ map, show, onShow, onHome }) {
  const [view, setView] = useState({ bearing: 0, pitch: 0 })
  useEffect(() => {
    if (!map) return
    const read = () => setView({ bearing: Math.round(((map.getBearing() % 360) + 360) % 360), pitch: Math.round(map.getPitch()) })
    read()
    map.on('move', read)
    return () => map.off('move', read)
  }, [map])
  const zoom = (d) => map?.easeTo({ zoom: map.getZoom() + d })
  return (
    <div className="pointer-events-auto absolute left-3 top-[5rem] z-10 flex w-36 flex-col gap-2 rounded-2xl border border-line bg-chalk p-2 shadow-lg md:bottom-3 md:top-auto">
      <div className="grid grid-cols-2 gap-2">
        <button type="button" aria-label="Zoom in" onClick={() => zoom(1)} className={btn}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => zoom(-1)} className={btn}>−</button>
      </div>
      <button type="button" onClick={onHome} className={`${btn} text-left`}>Reset view</button>
      <Toggle on={show.boundaries} onChange={(v) => onShow({ ...show, boundaries: v })}>Boundaries</Toggle>
      <Toggle on={show.buildings} onChange={(v) => onShow({ ...show, buildings: v })}>Buildings</Toggle>
      <p className="px-1 font-mono text-xs text-muted" aria-label="Camera">{view.bearing}° bearing · {view.pitch}° pitch</p>
    </div>
  )
}
