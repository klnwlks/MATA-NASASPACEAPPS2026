import { useEffect, useState } from 'react'
import { Pause, Play, Satellite, SkipBack, SkipForward } from 'lucide-react'
import { phtTime } from '../data.js'

const btn = 'grid size-9 place-items-center rounded-xl bg-page text-ink hover:bg-cobalt-tint hover:text-cobalt disabled:cursor-not-allowed disabled:text-muted disabled:opacity-60'
const STEP_MS = 900

// Stops are observed acquisition dates only. The gap to the previous pass is printed so 6- and 12-day jumps never read as daily.
export default function Timeline({ floods, frame, onFrame }) {
  const [playing, setPlaying] = useState(false)
  const frames = floods?.frames ?? []
  const last = frames.length - 1
  useEffect(() => {
    if (!playing) return
    const t = setInterval(() => onFrame((i) => (i >= last ? 0 : i + 1)), STEP_MS)
    return () => clearInterval(t)
  }, [playing, last, onFrame])
  const f = frames[frame]
  const ready = frames.length > 0
  return (
    <div role="group" aria-label="Flood replay" className="pointer-events-auto absolute inset-x-3 bottom-3 z-10 flex items-center gap-3 rounded-2xl bg-chalk p-2.5 shadow-float md:inset-x-auto md:left-1/2 md:w-[46rem] md:-translate-x-1/2">
      <span className="hidden items-center gap-2 rounded-xl bg-cobalt-tint px-3 py-2 text-sm font-medium text-cobalt-ink sm:flex" title={f?.track === 142 ? 'Ascending track 142, evening pass' : 'Descending track 32, morning pass'}><Satellite aria-hidden size={16} />S1 · {f?.track === 142 ? 'A142' : 'D32'}</span>
      <div className="flex gap-1.5">
        <button type="button" disabled={!ready} aria-label="Previous observation" onClick={() => onFrame((i) => Math.max(0, i - 1))} className={btn}><SkipBack aria-hidden size={18} /></button>
        <button type="button" disabled={!ready} aria-label={playing ? 'Pause replay' : 'Play replay'} onClick={() => setPlaying((p) => !p)} className={btn}>{playing ? <Pause aria-hidden size={18} /> : <Play aria-hidden size={18} />}</button>
        <button type="button" disabled={!ready} aria-label="Next observation" onClick={() => onFrame((i) => Math.min(last, i + 1))} className={btn}><SkipForward aria-hidden size={18} /></button>
      </div>
      <input type="range" disabled={!ready} min={0} max={Math.max(last, 0)} value={frame} onChange={(e) => onFrame(Number(e.target.value))} aria-label="Observation date" aria-valuetext={f ? phtTime(f.utc) : 'No observations loaded'} className="min-w-0 flex-1 accent-cobalt" />
      <div aria-live="polite" className="w-44 shrink-0 leading-tight">
        {f ? (
          <>
            <p className="whitespace-nowrap font-mono text-sm font-medium">{phtTime(f.utc)}</p>
            <p className="text-xs text-muted">{f.platform.replace('SENTINEL-', 'S')} · {f.daysSincePrevious == null ? 'first pass' : `${f.daysSincePrevious} d after previous`} · {frame + 1}/{frames.length}</p>
          </>
        ) : (
          <>
            <p className="text-sm font-medium">Replay · offline</p>
            <p className="text-xs text-muted">Observations: none loaded</p>
          </>
        )}
      </div>
    </div>
  )
}
