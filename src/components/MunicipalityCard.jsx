import { CloudLightning, Play, X } from 'lucide-react'
import { shortDate } from '../data.js'

// Observed flood runs across the municipality, from the province states (one character per frame per barangay):
// a run starts on any pass where at least one barangay is flooded by any source.
function runs(states, psgcs, frames) {
  const out = []
  frames.forEach((f, i) => {
    const flooded = psgcs.filter((id) => states[id]?.[i] === '1').length
    if (!flooded) return
    const prev = out.at(-1)
    if (prev && prev.end === i - 1) Object.assign(prev, { end: i, peak: Math.max(prev.peak, flooded) })
    else out.push({ start: i, end: i, peak: flooded })
  })
  return out
}

export default function MunicipalityCard({ municipality, psgcs, floods, onFrame, onClose }) {
  const events = floods ? runs(floods.states, psgcs, floods.frames) : []
  const assessed = floods && psgcs.some((id) => floods.states[id]?.includes('0') || floods.states[id]?.includes('1'))
  return (
    <aside aria-label="Observed flood signals" className="pointer-events-auto fixed inset-x-0 bottom-[4.75rem] z-10 flex max-h-[45vh] flex-col overflow-hidden rounded-t-2xl bg-chalk shadow-float md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl">
      <div className="overflow-y-auto p-4">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-cobalt text-white"><CloudLightning aria-hidden size={20} /></span>
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-medium leading-tight">{municipality.name}</h2>
            <p className="text-sm text-muted">Observed flood signals · {psgcs.length} barangays · Sentinel-1</p>
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
        </div>
        <p className="mt-2 text-xs text-muted">Consecutive flagged passes do not establish continuous flooding between them.</p>
        <ul className="mt-3 divide-y divide-line">
          {floods && !events.length && <li className="py-2 text-sm text-muted">{assessed ? 'No assessed barangay was flagged on any pass.' : 'No observations loaded for this municipality.'} Unknown is not dry.</li>}
          {events.map((e) => (
            <li key={e.start} className="flex items-center gap-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{shortDate(floods.frames[e.start].utc)}{e.end > e.start && ` – ${shortDate(floods.frames[e.end].utc)}`}</p>
                <p className="text-muted">{e.end - e.start + 1} pass{e.end > e.start ? 'es' : ''} · up to {e.peak} barangay{e.peak > 1 ? 's' : ''} with a flood signal</p>
              </div>
              <button type="button" onClick={() => onFrame(e.start)} className="flex items-center gap-1 rounded-lg bg-cobalt-tint px-2 py-1 text-cobalt hover:bg-cobalt hover:text-white"><Play aria-hidden size={14} />Show</button>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted">{floods ? `${floods.frames.length} passes, ${shortDate(floods.frames[0].utc)} – ${shortDate(floods.frames.at(-1).utc)}, Philippine time. Storm names are not inferred.` : 'No observations loaded. Empty ≠ dry.'}</p>
      </div>
    </aside>
  )
}
