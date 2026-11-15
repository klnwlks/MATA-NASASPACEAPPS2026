import { useEffect, useState } from 'react'
import { Building2, Compass, Grid3x3, Minus, Moon, Plus, Rows3, Shapes, Sun } from 'lucide-react'

const btn = 'grid size-10 place-items-center rounded-xl text-ink hover:bg-cobalt-tint hover:text-cobalt'

function Toggle({ on, onChange, label, tone, children }) {
  return (
    <button type="button" aria-pressed={on} aria-label={label} title={label} onClick={() => onChange(!on)} className={`${btn} ${on ? tone : 'text-muted'}`}>
      {children}
    </button>
  )
}

const clock = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`

// Time of day for lighting. Follows the selected pass's acquisition time until the slider is moved.
function TimeOfDay({ minutes, onMinutes, followingPass, onFollowPass }) {
  const [open, setOpen] = useState(false)
  const day = minutes >= 6 * 60 && minutes < 18 * 60
  const Icon = day ? Sun : Moon
  return (
    <div className="relative">
      <button type="button" aria-expanded={open} aria-label={`Time of day ${clock(minutes)}`} title="Time of day" onClick={() => setOpen(!open)} className={`${btn} ${open ? 'bg-amber-tint text-amber-ink' : ''}`}>
        <Icon aria-hidden size={20} />
      </button>
      {open && (
        <div className="absolute left-14 top-0 flex w-64 flex-col gap-2 rounded-2xl bg-chalk px-4 py-3 shadow-float">
          <label className="flex items-center gap-3">
            <span className="sr-only">Time of day, Manila</span>
            <input type="range" min={0} max={1435} step={5} value={minutes} onChange={(e) => onMinutes(Number(e.target.value))} className="w-full accent-cobalt" />
            <output className="font-mono text-xs text-ink">{clock(minutes)}</output>
          </label>
          {onFollowPass && (
            <button type="button" aria-pressed={followingPass} onClick={onFollowPass} className={`rounded-lg px-2 py-1 text-left text-xs ${followingPass ? 'bg-cobalt-tint text-cobalt' : 'text-ink hover:bg-cobalt-tint'}`}>
              {followingPass ? 'Following satellite pass' : 'Match satellite pass'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function MapControls({ map, show, onShow, onHome, minutes, onMinutes, followingPass, onFollowPass, hasCoherence, hasNisar }) {
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
      {hasCoherence && <Toggle on={show.coherence} onChange={(v) => onShow({ ...show, coherence: v })} label="Built-up coherence loss" tone="bg-amber-tint text-amber-ink"><Rows3 aria-hidden size={20} /></Toggle>}
      {hasNisar && <Toggle on={show.nisar} onChange={(v) => onShow({ ...show, nisar: v })} label="NISAR L-band darkening" tone="bg-cobalt-tint text-cobalt"><Grid3x3 aria-hidden size={20} /></Toggle>}
      <TimeOfDay minutes={minutes} onMinutes={onMinutes} followingPass={followingPass} onFollowPass={onFollowPass} />
      <p className="mt-1 text-center font-mono text-[10px] leading-tight text-muted" aria-label={`Bearing ${view.bearing} degrees, pitch ${view.pitch} degrees`}>{view.bearing}°<br />{view.pitch}°</p>
    </div>
  )
}
