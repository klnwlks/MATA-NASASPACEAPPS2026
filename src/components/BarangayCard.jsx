import { Crosshair, Hash, MapPin, Radar, Shapes, Landmark, X } from 'lucide-react'
import { DATA_VERSION, shortDate } from '../data.js'

function Row({ icon: Icon, tone, label, children, mono }) {
  return (
    <div className="flex items-center gap-3 py-2 text-sm">
      <span className={`grid size-8 shrink-0 place-items-center rounded-lg ${tone}`}><Icon aria-hidden size={16} /></span>
      <dt className="text-muted">{label}</dt>
      <dd className={`ml-auto text-right ${mono ? 'font-mono' : ''}`}>{children}</dd>
    </div>
  )
}

const STATE = { 1: ['Flooded', 'bg-cobalt text-white'], 0: ['No flood detected', 'bg-page text-ink'], [-1]: ['Unknown', 'bg-page text-muted'] }
const range = (e) => (e.maxDays == null ? `at least ${e.minDays} d, upper bound unknown` : `between ${e.minDays} and ${e.maxDays} days`)

// Observed state on the current frame, and every flooded run as a duration range bounded by real passes.
function Observations({ rec, frame, frames, onFrame }) {
  const [label, tone] = STATE[rec.state[frame]]
  return (
    <section className="mt-4 rounded-xl bg-cobalt-tint p-3">
      <div className="flex items-center gap-2">
        <Radar aria-hidden size={16} className="text-cobalt-ink" />
        <h3 className="text-sm font-medium text-cobalt-ink">This pass</h3>
        <span className={`ml-auto rounded-lg px-2 py-0.5 text-xs font-medium ${tone}`}>{label}</span>
      </div>
      <p className="mt-1 font-mono text-sm">{rec.floodHa[frame]} ha flood · {rec.lowConfidenceHa[frame]} ha low-confidence</p>
      <p className="text-xs text-muted">Low confidence: water on cropland or wetland, often paddies. {Math.round(rec.validShare[frame] * 100)} % of the barangay assessed.</p>
      <h3 className="mt-3 text-sm font-medium text-cobalt-ink">Flooded runs, {frames.length} passes</h3>
      {rec.episodes.length ? (
        <ul className="mt-1 divide-y divide-line/70">
          {rec.episodes.map((e) => (
            <li key={e.first}>
              <button type="button" onClick={() => onFrame(frames.findIndex((f) => f.utc === e.first))} className="w-full py-1.5 text-left text-sm hover:text-cobalt">
                <span className="font-medium">{shortDate(e.first)}{e.last !== e.first && ` – ${shortDate(e.last)}`}</span>
                <span className="block text-xs text-muted">{range(e)} · {e.observations} pass{e.observations > 1 ? 'es' : ''}{e.unknownInside ? ' · unassessed pass inside' : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">No flooded pass detected. Urban and vegetated flooding can hide from radar.</p>
      )}
    </section>
  )
}

function Selected({ barangay, rec, frame, frames, onClose, onLocate, onFrame }) {
  return (
    <div className="overflow-y-auto p-4">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-cobalt text-white"><MapPin aria-hidden size={20} /></span>
        <h2 className="min-w-0 flex-1 text-xl font-medium leading-tight">{barangay.name}</h2>
        <button type="button" aria-label="Close" onClick={onClose} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
      </div>
      <dl className="mt-3 divide-y divide-line">
        <Row icon={Hash} tone="bg-cobalt-tint text-cobalt" label="PSGC" mono>{barangay.psgc}</Row>
        <Row icon={Landmark} tone="bg-mint-tint text-mint-ink" label="Municipality">{barangay.municipality}, Laguna</Row>
        <Row icon={Shapes} tone="bg-amber-tint text-amber-ink" label="Geometry">{DATA_VERSION.source}, {DATA_VERSION.validOn}</Row>
      </dl>
      <button type="button" onClick={onLocate} className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-cobalt px-3 py-2 text-sm font-medium text-white hover:bg-cobalt-ink"><Crosshair aria-hidden size={16} />Locate on map</button>
      {rec ? (
        <Observations rec={rec} frame={frame} frames={frames} onFrame={onFrame} />
      ) : (
        <section className="mt-4 flex gap-3 rounded-xl bg-coral-tint p-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/70 text-coral-ink"><Radar aria-hidden size={16} /></span>
          <div>
            <h3 className="text-sm font-medium text-coral-ink">Observations</h3>
            <p className="mt-0.5 text-sm">No observations loaded</p>
            <p className="text-sm text-muted">Empty ≠ dry.</p>
          </div>
        </section>
      )}
    </div>
  )
}

export default function BarangayCard({ list, floods, frame, selectedId, onClose, onLocate, onFrame }) {
  const barangay = list.find((b) => b.psgc === selectedId)
  if (!barangay) return null
  return (
    <aside aria-label="Barangay details" className="pointer-events-auto fixed inset-x-0 bottom-[4.75rem] z-10 flex max-h-[45vh] flex-col overflow-hidden rounded-t-2xl bg-chalk shadow-float md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl">
      <Selected barangay={barangay} rec={floods?.barangays[barangay.psgc]} frame={frame} frames={floods?.frames ?? []} onClose={onClose} onLocate={() => onLocate(barangay)} onFrame={onFrame} />
    </aside>
  )
}
