import { DATA_VERSION } from '../data.js'

const card = 'pointer-events-auto flex flex-col overflow-hidden border border-line bg-chalk shadow-lg'

function Row({ label, children, mono }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className={mono ? 'font-mono' : ''}>{children}</dd>
    </div>
  )
}

function Empty({ list, onSelect }) {
  return (
    <>
      <div className="p-4 pb-2">
        <h2 className="text-lg font-medium">No barangay selected</h2>
        <p className="mt-1 text-sm text-muted">{list.length} barangays · Los Baños, Laguna. Select on map or list.</p>
      </div>
      <ul className="overflow-y-auto px-2 pb-2">
        {list.map((b) => (
          <li key={b.psgc}>
            <button type="button" onClick={() => onSelect(b.psgc, true)} className="flex w-full items-baseline justify-between gap-3 rounded-lg px-2 py-2 text-left text-sm hover:bg-cobalt-tint">
              <span>{b.name}</span>
              <span className="font-mono text-xs text-muted">{b.psgc}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

function Selected({ barangay, onClose, onLocate }) {
  return (
    <div className="overflow-y-auto p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-xl font-medium">{barangay.name}</h2>
        <button type="button" onClick={onClose} className="rounded-lg border border-line px-2.5 py-1 text-sm hover:bg-cobalt-tint">Close</button>
      </div>
      <dl className="mt-3">
        <Row label="PSGC" mono>{barangay.psgc}</Row>
        <Row label="Municipality">{barangay.municipality}, Laguna</Row>
        <Row label="Geometry">{DATA_VERSION.source}, {DATA_VERSION.validOn}</Row>
      </dl>
      <button type="button" onClick={onLocate} className="mt-3 rounded-lg bg-cobalt px-3 py-1.5 text-sm font-medium text-white hover:bg-cobalt-ink">Locate on map</button>
      <section className="mt-4 rounded-xl bg-cobalt-tint p-3">
        <h3 className="text-sm font-medium text-cobalt-ink">Observations</h3>
        <p className="mt-1 text-sm">No storm observations loaded</p>
        <p className="text-sm text-muted">Flood extent: not in this build. Empty ≠ dry.</p>
      </section>
    </div>
  )
}

export default function BarangayCard({ list, selectedId, onSelect, onClose, onLocate }) {
  const barangay = list.find((b) => b.psgc === selectedId)
  const place = barangay
    ? 'fixed inset-x-0 bottom-[3.75rem] max-h-[45vh] rounded-t-2xl md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl'
    : 'hidden md:absolute md:right-3 md:top-[5rem] md:flex md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl'
  return (
    <aside aria-label="Barangay details" className={`${card} ${place} z-10`}>
      {barangay ? <Selected barangay={barangay} onClose={onClose} onLocate={() => onLocate(barangay)} /> : <Empty list={list} onSelect={onSelect} />}
    </aside>
  )
}
