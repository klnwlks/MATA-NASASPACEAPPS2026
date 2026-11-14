import { Crosshair, Hash, MapPin, Radar, Shapes, Landmark, X } from 'lucide-react'
import { DATA_VERSION } from '../data.js'

function Row({ icon: Icon, tone, label, children, mono }) {
  return (
    <div className="flex items-center gap-3 py-2 text-sm">
      <span className={`grid size-8 shrink-0 place-items-center rounded-lg ${tone}`}><Icon aria-hidden size={16} /></span>
      <dt className="text-muted">{label}</dt>
      <dd className={`ml-auto text-right ${mono ? 'font-mono' : ''}`}>{children}</dd>
    </div>
  )
}

function Selected({ barangay, onClose, onLocate }) {
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
      <section className="mt-4 flex gap-3 rounded-xl bg-coral-tint p-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-white/70 text-coral-ink"><Radar aria-hidden size={16} /></span>
        <div>
          <h3 className="text-sm font-medium text-coral-ink">Observations</h3>
          <p className="mt-0.5 text-sm">No storm observations loaded</p>
          <p className="text-sm text-muted">Flood extent: not in this build. Empty ≠ dry.</p>
        </div>
      </section>
    </div>
  )
}

export default function BarangayCard({ list, selectedId, onClose, onLocate }) {
  const barangay = list.find((b) => b.psgc === selectedId)
  if (!barangay) return null
  return (
    <aside aria-label="Barangay details" className="pointer-events-auto fixed inset-x-0 bottom-[4.75rem] z-10 flex max-h-[45vh] flex-col overflow-hidden rounded-t-2xl bg-chalk shadow-float md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl">
      <Selected barangay={barangay} onClose={onClose} onLocate={() => onLocate(barangay)} />
    </aside>
  )
}
