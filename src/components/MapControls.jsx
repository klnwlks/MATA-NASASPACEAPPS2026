import { useEffect, useState } from 'react'
import { Building2, Compass, Minus, Plus, Shapes } from 'lucide-react'

const btn = 'grid size-10 place-items-center rounded-xl text-ink hover:bg-cobalt-tint hover:text-cobalt'

function Toggle({ on, onChange, label, tone, children }) {
  return (
    <button type="button" aria-pressed={on} aria-label={label} title={label} onClick={() => onChange(!on)} className={`${btn} ${on ? tone : 'text-muted'}`}>
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
    <div className="pointer-events-auto absolute left-3 top-[5rem] z-10 flex w-14 flex-col items-center gap-1 rounded-2xl bg-chalk p-2 shadow-float md:bottom-3 md:top-auto">
      <button type="button" aria-label="Zoom in" title="Zoom in" onClick={() => zoom(1)} className={btn}><Plus aria-hidden size={20} /></button>
      <button type="button" aria-label="Zoom out" title="Zoom out" onClick={() => zoom(-1)} className={btn}><Minus aria-hidden size={20} /></button>
      <button type="button" aria-label="Reset view" title="Reset view" onClick={onHome} className={`${btn} text-coral-ink hover:bg-coral-tint hover:text-coral-ink`}>
        <Compass aria-hidden size={20} style={{ transform: `rotate(${view.bearing - 180}deg)` }} />
      </button>
      <span className="my-1 h-px w-6 bg-line" aria-hidden />
      <Toggle on={show.boundaries} onChange={(v) => onShow({ ...show, boundaries: v })} label="Boundaries" tone="bg-cobalt-tint text-cobalt"><Shapes aria-hidden size={20} /></Toggle>
      <Toggle on={show.buildings} onChange={(v) => onShow({ ...show, buildings: v })} label="Buildings" tone="bg-amber-tint text-amber-ink"><Building2 aria-hidden size={20} /></Toggle>
      <p className="mt-1 text-center font-mono text-[10px] leading-tight text-muted" aria-label={`Bearing ${view.bearing} degrees, pitch ${view.pitch} degrees`}>{view.bearing}°<br />{view.pitch}°</p>
    </div>
  )
}
