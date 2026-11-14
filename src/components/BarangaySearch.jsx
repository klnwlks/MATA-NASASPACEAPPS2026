import { useId, useState } from 'react'
import { MapPin, Search } from 'lucide-react'

export default function BarangaySearch({ list, disabled, onSelect }) {
  const id = useId()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const term = q.trim().toLowerCase()
  const hits = term ? list.filter((b) => b.name.toLowerCase().includes(term) || b.psgc.includes(term)) : []
  const showList = open && term
  const choose = (b) => {
    onSelect(b.psgc, true)
    setQ('')
    setOpen(false)
  }
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, hits.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && showList && hits[active]) { e.preventDefault(); choose(hits[active]) }
    else if (e.key === 'Escape') setOpen(false)
  }
  return (
    <div className="relative min-w-0 flex-1 md:max-w-md">
      <Search aria-hidden size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-cobalt" />
      <input
        role="combobox"
        aria-expanded={!!showList}
        aria-controls={`${id}-list`}
        aria-activedescendant={showList && hits[active] ? `${id}-${hits[active].psgc}` : undefined}
        aria-label="Search barangays"
        autoComplete="off"
        disabled={disabled}
        value={q}
        placeholder="Barangay or PSGC"
        onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKey}
        className="w-full rounded-xl bg-cobalt-tint py-2.5 pl-10 pr-3 text-sm font-medium text-ink placeholder:font-normal placeholder:text-cobalt-ink/70 focus:bg-white focus:outline-2 focus:outline-cobalt disabled:opacity-60"
      />
      {showList && (
        <ul id={`${id}-list`} role="listbox" aria-label="Matching barangays" className="absolute inset-x-0 top-full z-30 mt-2 max-h-72 overflow-y-auto rounded-xl bg-chalk p-1.5 shadow-float">
          {hits.length === 0 && <li className="px-3 py-2 text-sm text-muted">No barangay matches “{q}”.</li>}
          {hits.map((b, i) => (
            <li key={b.psgc} id={`${id}-${b.psgc}`} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); choose(b) }} onMouseEnter={() => setActive(i)} className={`flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm ${i === active ? 'bg-cobalt-tint' : ''}`}>
              <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-cobalt-tint text-cobalt"><MapPin aria-hidden size={15} /></span>
              <span className="flex-1">{b.name}</span>
              <span className="font-mono text-xs text-muted">{b.psgc}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
