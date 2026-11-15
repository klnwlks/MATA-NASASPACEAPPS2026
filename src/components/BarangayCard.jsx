import { Crosshair, MapPin, Radar, Shapes, Landmark, X } from 'lucide-react'
import { DATA_VERSION, shortDate, stateAt } from '../data.js'
import SecondOpinions from './SecondOpinions.jsx'

function Row({ icon: Icon, tone, label, children, mono }) {
  return (
    <div className="flex items-center gap-3 py-2 text-sm">
      <span className={`grid size-8 shrink-0 place-items-center rounded-lg ${tone}`}><Icon aria-hidden size={16} /></span>
      <dt className="text-muted">{label}</dt>
      <dd className={`ml-auto text-right ${mono ? 'font-mono' : ''}`}>{children}</dd>
    </div>
  )
}

const STATE = { 1: ['Flood signal', 'bg-cobalt text-white'], 0: ['Below threshold', 'bg-page text-ink'], [-1]: ['Unknown', 'bg-page text-muted'] }
const SOURCE = { openWater: 'Sentinel-1 radar', opera: 'OPERA', coherence: 'radar coherence', nisar: 'NISAR' }
const sources = (keys) => keys.map((k) => SOURCE[k] ?? k).join(', ')
const fmt = (n) => n.toLocaleString('en-PH', { maximumFractionDigits: n < 10 ? 1 : 0 })
// One football field is about 0.71 ha, a size people can picture.
const fields = (ha) => (ha < 0.4 ? 'less than half a football field' : `about ${fmt(ha / 0.714)} football field${ha / 0.714 < 1.5 ? '' : 's'}`)
const lasted = (e) => (e.maxDays == null ? `at least ${e.minDays} days` : e.minDays === e.maxDays ? `${e.minDays} days` : `${e.minDays}–${e.maxDays} days`)
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`

// What radar says about this barangay right now, in everyday words.
function Now({ rec, frame }) {
  const state = rec.state[frame]
  const ha = rec.floodHa[frame]
  const share = rec.areaHa ? (ha / rec.areaHa) * 100 : null
  const r = rec.floodHaRange?.[frame]
  const maybe = rec.lowConfidenceHa[frame]
  const seen = Math.round(rec.visibleShare[frame] * 100)
  const [headline, sentence] =
    state === 1 ? ['Likely flooded', `Radar found about ${fmt(ha)} ha of standing water (${fields(ha)})${share != null ? `, ${share < 0.1 ? 'under 0.1' : fmt(share)}% of the barangay` : ''}.`]
    : state === 0 ? ['No flooding detected', ha > 0 ? `Only ${fmt(ha)} ha of water showed up, within what this area normally shows in the dry season.` : 'No unusual water showed up on this pass.']
    : ['Cannot tell', seen < 15 ? 'Too little of the ground was visible to radar on this pass to judge.' : 'There was no usable radar pass for this barangay at this time. That does not mean it stayed dry.']
  return (
    <>
      <p className="mt-2 text-base font-medium">{headline}</p>
      <p className="text-sm">{sentence}</p>
      {state !== -1 && r && r[1] > r[0] && <p className="mt-1 text-sm text-muted">With stricter or looser settings the answer ranges from {fmt(r[0])} to {fmt(r[1])} ha{r[0] === 0 && state === 1 ? ', so treat this as a possible, not certain, flood' : ''}.</p>}
      {state !== -1 && maybe >= 0.5 && <p className="text-sm text-muted">Another {fmt(maybe)} ha looked wet but is too unclear to count.</p>}
      {state !== -1 && <p className="text-sm text-muted">Radar can see about {seen}% of the ground here; water under buildings or trees stays hidden.</p>}
    </>
  )
}

// The barangay's track record over the whole period: how often, how long, how bad.
function History({ rec, frames, onFrame }) {
  const assessed = rec.state.filter((s) => s !== -1).length
  const flagged = rec.state.filter((s) => s === 1).length
  let peak = -1
  rec.state.forEach((s, i) => { if (s === 1 && (peak < 0 || rec.floodHa[i] > rec.floodHa[peak])) peak = i })
  const eps = rec.episodes ?? []
  const last = eps.at(-1)
  const longest = eps.reduce((a, e) => (!a || (e.maxDays ?? e.minDays) > (a.maxDays ?? a.minDays) ? e : a), null)
  const go = (utc) => onFrame(frames.findIndex((f) => f.utc === utc))
  const fact = 'flex w-full items-baseline justify-between gap-3 py-1.5 text-left text-sm'
  if (!flagged) return <p className="mt-3 text-sm text-muted">Radar did not flag flooding here on any of the {assessed} passes it could judge since {shortDate(frames[0].utc)}.</p>
  return (
    <>
      <h3 className="mt-3 text-sm font-medium text-cobalt-ink">Flood history</h3>
      <p className="text-sm">Flagged on {flagged} of {assessed} judged passes{eps.length ? `, in ${plural(eps.length, 'separate episode')}` : ''}.</p>
      <ul className="mt-1 divide-y divide-line/70">
        {last && <li><button type="button" onClick={() => go(last.first)} className={`${fact} hover:text-cobalt`}><span className="text-muted">Most recent</span><span className="text-right font-medium">{shortDate(last.first)}{last.last !== last.first && ` – ${shortDate(last.last)}`}</span></button></li>}
        {longest && <li><button type="button" onClick={() => go(longest.first)} className={`${fact} hover:text-cobalt`}><span className="text-muted">Longest</span><span className="text-right font-medium">{lasted(longest)}, from {shortDate(longest.first)}</span></button></li>}
        {peak >= 0 && <li><button type="button" onClick={() => onFrame(peak)} className={`${fact} hover:text-cobalt`}><span className="text-muted">Widest</span><span className="text-right font-medium">{fmt(rec.floodHa[peak])} ha on {shortDate(frames[peak].utc)}</span></button></li>}
      </ul>
    </>
  )
}

function Observations({ rec, frame, frames, onFrame }) {
  const [label, tone] = STATE[rec.state[frame]]
  const eps = rec.episodes ?? []
  return (
    <section className="mt-4 rounded-xl bg-cobalt-tint p-3">
      <div className="flex items-center gap-2">
        <Radar aria-hidden size={16} className="text-cobalt-ink" />
        <h3 className="text-sm font-medium text-cobalt-ink">On {shortDate(frames[frame].utc)}</h3>
        <span className={`ml-auto rounded-lg px-2 py-0.5 text-xs font-medium ${tone}`}>{label}</span>
      </div>
      <Now rec={rec} frame={frame} />
      {rec.seenBy[frame].length > 0 && <p className="mt-1 text-xs text-cobalt-ink">Detected by {sources(rec.seenBy[frame])}</p>}
      <SecondOpinions evidence={rec.evidence} frame={frame} />
      <History rec={rec} frames={frames} onFrame={onFrame} />
      {eps.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-cobalt-ink">All {plural(eps.length, 'episode')}</summary>
          <ul className="mt-1 divide-y divide-line/70">
            {eps.map((e) => (
              <li key={e.first}>
                <button type="button" onClick={() => onFrame(frames.findIndex((f) => f.utc === e.first))} className="w-full py-1.5 text-left hover:text-cobalt">
                  <span className="font-medium">{shortDate(e.first)}{e.last !== e.first && ` – ${shortDate(e.last)}`}</span>
                  <span className="block text-xs text-muted">Lasted {lasted(e)} · flagged on {plural(e.observations, 'pass')}{e.unknownInside ? ' · one pass in between could not be judged' : ''}</span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
      {rec.episodes == null && <p className="mt-2 text-sm text-muted">How long past floods lasted is not available here.</p>}
      <details className="mt-3 text-xs text-muted">
        <summary className="cursor-pointer text-cobalt-ink">How reliable is this?</summary>
        <p className="mt-1">Satellites pass every few days, so durations are estimates between two passes, not exact. A barangay is flagged when a meaningful area of clear water appears, well above its normal dry-season readings. The rule is deliberately lenient, so false alarms are possible.</p>
        <p className="mt-1">Radar cannot see under buildings or trees, and farm fields or ponds can look like floodwater. These are early signals, not ground-verified reports.</p>
      </details>
    </section>
  )
}

// Until the municipality's record arrives (or if it never does), the province summary still gives this pass's state.
function Summary({ state, status, municipality }) {
  if (state == null)
    return (
      <section className="mt-4 flex gap-3 rounded-xl bg-coral-tint p-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/70 text-coral-ink"><Radar aria-hidden size={16} /></span>
        <div>
          <h3 className="text-sm font-medium text-coral-ink">Observations</h3>
          <p className="mt-0.5 text-sm">No observations loaded</p>
          <p className="text-sm text-muted">Empty ≠ dry.</p>
        </div>
      </section>
    )
  const [label, tone] = STATE[state]
  const bad = status !== 'loading'
  return (
    <section className={`mt-4 rounded-xl p-3 ${bad ? 'bg-coral-tint' : 'bg-cobalt-tint'}`}>
      <div className="flex items-center gap-2">
        <Radar aria-hidden size={16} className={bad ? 'text-coral-ink' : 'text-cobalt-ink'} />
        <h3 className={`text-sm font-medium ${bad ? 'text-coral-ink' : 'text-cobalt-ink'}`}>This pass</h3>
        <span className={`ml-auto rounded-lg px-2 py-0.5 text-xs font-medium ${tone}`}>{label}</span>
      </div>
      <p className="mt-1 text-sm text-muted">{bad ? `No detailed record for this barangay from ${municipality}, so flooded runs and hectares are not shown. Empty ≠ dry.` : 'Loading flooded runs and open-water hectares…'}</p>
    </section>
  )
}

function Selected({ barangay, rec, state, status, frame, frames, onClose, onLocate, onFrame }) {
  return (
    <div className="overflow-y-auto p-4">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-cobalt text-white"><MapPin aria-hidden size={20} /></span>
        <h2 className="min-w-0 flex-1 text-xl font-medium leading-tight">{barangay.name}</h2>
        <button type="button" aria-label="Close" onClick={onClose} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
      </div>
      <dl className="mt-3 divide-y divide-line">
        <Row icon={Landmark} tone="bg-mint-tint text-mint-ink" label="Municipality">{barangay.municipality}, Laguna</Row>
        {rec?.areaHa != null && <Row icon={Shapes} tone="bg-amber-tint text-amber-ink" label="Size">{fmt(rec.areaHa / 100)} km² ({fmt(rec.areaHa)} ha)</Row>}
      </dl>
      <button type="button" onClick={onLocate} className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-cobalt px-3 py-2 text-sm font-medium text-white hover:bg-cobalt-ink"><Crosshair aria-hidden size={16} />Locate on map</button>
      {rec ? <Observations rec={rec} frame={frame} frames={frames} onFrame={onFrame} /> : <Summary state={state} status={status} municipality={barangay.municipality} />}
      <p className="mt-3 text-xs text-muted">Barangay code {barangay.psgc} · boundaries {DATA_VERSION.source}, {DATA_VERSION.validOn}</p>
    </div>
  )
}

export default function BarangayCard({ barangay, states, manifest, frames, frame, onClose, onLocate, onFrame }) {
  const rec = manifest?.data?.barangays[barangay.psgc]
  return (
    <aside aria-label="Barangay details" className="pointer-events-auto fixed inset-x-0 bottom-0 z-40 flex max-h-[45vh] flex-col overflow-hidden rounded-t-2xl bg-chalk shadow-float md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:z-10 md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl">
      <Selected barangay={barangay} rec={rec} state={states ? stateAt(states, barangay.psgc, frame) : null} status={manifest?.status ?? 'loading'} frame={frame} frames={frames} onClose={onClose} onLocate={() => onLocate(barangay)} onFrame={onFrame} />
    </aside>
  )
}
