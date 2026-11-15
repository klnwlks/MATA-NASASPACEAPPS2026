import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Landmark, MapPin, Search } from 'lucide-react'

const MAX_SHOWN = 30
const plain = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase() // "banos" finds Los Baños

// Barangay names repeat across the province (Poblacion, San Antonio), so every result names its municipality, and a
// municipality is a result of its own. All typed words must match the name, the municipality or the PSGC.
function useIndex(list, municipalities) {
  return useMemo(
    () => [
      ...municipalities.map((m) => ({ kind: 'municipality', key: m.psgc, name: m.name, sub: 'Municipality', code: m.psgc, ref: m, hay: plain(`${m.name} ${m.psgc}`), lead: plain(m.name) })),
      ...list.map((b) => ({ kind: 'barangay', key: b.psgc, name: b.name, sub: b.municipality, code: b.psgc, ref: b, hay: plain(`${b.name} ${b.municipality} ${b.psgc}`), lead: plain(b.name) })),
    ],
    [list, municipalities],
  )
}

function search(index, q) {
  const words = plain(q).split(/\s+/).filter(Boolean)
  if (!words.length) return []
  const rank = (e) => (e.lead === words.join(' ') ? 0 : e.lead.startsWith(words[0]) ? 1 : 2) * 2 + (e.kind === 'municipality' ? 0 : 1)
  return index
    .filter((e) => words.every((w) => e.hay.includes(w)))
    .sort((a, b) => rank(a) - rank(b))
}

export default function BarangaySearch({ list, municipalities, disabled, onSelect, onMunicipality }) {
  const id = useId()
  const index = useIndex(list, municipalities)
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const activeEl = useRef(null)
  const all = useMemo(() => search(index, q), [index, q])
  const hits = all.slice(0, MAX_SHOWN)
  const showList = open && q.trim() !== ''
  useEffect(() => activeEl.current?.scrollIntoView({ block: 'nearest' }), [active, showList])
  const choose = (e) => {
    if (e.kind === 'municipality') onMunicipality(e.ref)
    else onSelect(e.ref.psgc, true)
    setQ('')
    setOpen(false)
  }
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((i) => (i + 1) % Math.max(hits.length, 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setOpen(true); setActive((i) => (i - 1 + hits.length) % Math.max(hits.length, 1)) }
    else if (e.key === 'Enter' && showList && hits[active]) { e.preventDefault(); choose(hits[active]) }
    else if (e.key === 'Escape') { if (open) { e.preventDefault(); setOpen(false) } else setQ('') }
  }
  return (
    <div className="relative min-w-0 flex-1 md:max-w-lg">
      <Search aria-hidden size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-cobalt" />
      <input
        role="combobox"
        aria-expanded={!!showList}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        aria-activedescendant={showList && hits[active] ? `${id}-${hits[active].key}` : undefined}
        aria-label="Search barangays and municipalities"
        autoComplete="off"
        disabled={disabled}
        value={q}
        placeholder="Barangay, municipality or PSGC"
        onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKey}
        className="w-full rounded-xl bg-cobalt-tint py-2.5 pl-10 pr-3 text-sm font-medium text-ink placeholder:font-normal placeholder:text-cobalt-ink/70 focus:bg-white focus:outline-2 focus:outline-cobalt disabled:opacity-60"
      />
      <p role="status" className="sr-only">{showList ? (all.length ? `${all.length} result${all.length > 1 ? 's' : ''}` : 'No results') : ''}</p>
      {showList && (
        <ul id={`${id}-list`} role="listbox" aria-label="Matching barangays and municipalities" className="absolute inset-x-0 top-full z-30 mt-2 max-h-80 overflow-y-auto rounded-xl bg-chalk p-1.5 shadow-float">
          {hits.length === 0 && <li className="px-3 py-2 text-sm text-muted">Nothing matches “{q}”.</li>}
          {hits.map((e, i) => {
            const Icon = e.kind === 'municipality' ? Landmark : MapPin
            return (
              <li key={e.key} id={`${id}-${e.key}`} ref={i === active ? activeEl : null} role="option" aria-selected={i === active} onMouseDown={(ev) => { ev.preventDefault(); choose(e) }} onMouseEnter={() => setActive(i)} className={`flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm ${i === active ? 'bg-cobalt-tint' : ''}`}>
                <span className={`grid size-7 shrink-0 place-items-center rounded-lg ${e.kind === 'municipality' ? 'bg-cobalt text-white' : 'bg-cobalt-tint text-cobalt'}`}><Icon aria-hidden size={15} /></span>
                <span className="min-w-0 flex-1 truncate"><span className="font-medium">{e.name}</span><span className="text-muted"> · {e.sub}</span></span>
                <span className="hidden font-mono text-xs text-muted sm:inline">{e.code}</span>
              </li>
            )
          })}
          {all.length > MAX_SHOWN && <li className="px-3 py-2 text-xs text-muted" role="presentation">{all.length - MAX_SHOWN} more. Type more of the name or the municipality.</li>}
        </ul>
      )}
    </div>
  )
}
