import { useState } from 'react'
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

const MD = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', month: 'short', day: 'numeric' })
const yearOf = (utc) => new Date(utc).toLocaleString('en-PH', { timeZone: 'Asia/Manila', year: 'numeric' })
const md = (utc) => MD.format(new Date(utc))
const FOLDED = 5

// One episode: whole row is the action; the bar is the share of barangays flagged at the peak.
function Episode({ e, frames, total, widest, onFrame }) {
  const a = frames[e.start].utc
  const b = frames[e.end].utc
  const span = e.end > e.start ? `${md(a)} – ${md(b)}${yearOf(a) !== yearOf(b) ? `, ${yearOf(b)}` : ''}` : md(a)
  return (
    <li>
      <button type="button" onClick={() => onFrame(e.start)} aria-label={`Show ${shortDate(a)}${e.end > e.start ? ` to ${shortDate(b)}` : ''}, ${e.peak} of ${total} barangays flagged`} className="group flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-cobalt-tint focus-visible:outline-2 focus-visible:outline-cobalt">
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{span}</span>
          {(e.end > e.start || widest) && <span className="block text-xs text-muted">{[e.end > e.start && `${e.end - e.start + 1} passes`, widest && 'Widest'].filter(Boolean).join(' · ')}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-2" aria-hidden>
          <span className="h-1.5 w-14 overflow-hidden rounded-full bg-line"><span className="block h-full rounded-full bg-cobalt" style={{ width: `${(e.peak / total) * 100}%` }} /></span>
          <span className="w-7 text-right text-xs tabular-nums text-muted">{e.peak}/{total}</span>
        </span>
        <Play aria-hidden size={14} className="shrink-0 text-muted group-hover:text-cobalt" />
      </button>
    </li>
  )
}

function Episodes({ events, frames, total, onFrame }) {
  const [all, setAll] = useState(false)
  const worst = events.reduce((a, e) => (e.peak > a.peak ? e : a))
  const newest = [...events].reverse()
  const shown = all ? newest : newest.slice(0, FOLDED)
  const years = [...new Set(shown.map((e) => yearOf(frames[e.start].utc)))]
  return (
    <>
      <p className="mt-4 text-sm"><span className="font-medium">{events.length} flood episodes</span> <span className="text-muted">· worst {worst.peak} of {total} barangays, {shortDate(frames[worst.start].utc)}</span></p>
      <div className="mt-1 flex items-center justify-between px-2 text-xs text-muted"><span>Newest first</span><span>Barangays flagged at peak</span></div>
      {years.map((y) => (
        <section key={y} aria-label={y}>
          <h3 className="mt-2 px-2 text-xs font-medium text-muted">{y}</h3>
          <ul>{shown.filter((e) => yearOf(frames[e.start].utc) === y).map((e) => <Episode key={e.start} e={e} frames={frames} total={total} widest={e === worst} onFrame={onFrame} />)}</ul>
        </section>
      ))}
      {newest.length > FOLDED && <button type="button" onClick={() => setAll(!all)} className="mt-2 w-full rounded-lg px-2 py-2 text-sm font-medium text-cobalt hover:bg-cobalt-tint">{all ? 'Show fewer' : `Show all ${newest.length} episodes`}</button>}
    </>
  )
}

export default function MunicipalityCard({ municipality, psgcs, floods, onFrame, onClose }) {
  const events = floods ? runs(floods.states, psgcs, floods.frames) : []
  const assessed = floods && psgcs.some((id) => floods.states[id]?.includes('0') || floods.states[id]?.includes('1'))
  return (
    <aside aria-label="Observed flood signals" className="pointer-events-auto fixed inset-x-0 bottom-0 z-40 flex max-h-[45vh] flex-col overflow-hidden rounded-t-2xl bg-chalk shadow-float md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:z-10 md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl">
      <div className="overflow-y-auto p-4">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-cobalt text-white"><CloudLightning aria-hidden size={20} /></span>
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-medium leading-tight">{municipality.name}</h2>
            <p className="text-sm text-muted">Observed flood signals · {psgcs.length} barangays · Sentinel-1</p>
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
        </div>
        <p className="mt-2 text-xs text-muted">Satellite radar flags likely floodwater per barangay. These are early signals, not confirmed reports, and gaps between passes are unknown.</p>
        {floods && events.length > 0 && <Episodes events={events} frames={floods.frames} total={psgcs.length} onFrame={onFrame} />}
        {floods && !events.length && <p className="mt-3 text-sm text-muted">{assessed ? 'No barangay here was flagged on any pass.' : 'No usable radar data for this municipality yet.'} A missing signal does not mean the area stayed dry.</p>}
        <p className="mt-3 text-xs text-muted">{floods ? `Covers ${shortDate(floods.frames[0].utc)} – ${shortDate(floods.frames.at(-1).utc)} (Philippine time). Storms are not named.` : 'No observations loaded. Empty does not mean dry.'}</p>
      </div>
    </aside>
  )
}
