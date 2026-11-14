import { useId, useState } from 'react'

export default function BarangaySearch({ list, disabled, onSelect }) {
  const id = useId()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const term = q.trim().toLowerCase()
  const hits = term ? list.filter((b) => b.name.toLowerCase().includes(term) || b.psgc.includes(term)) : list
  const choose = (b) => {
    onSelect(b.psgc, true)
    setQ('')
    setOpen(false)
  }
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, hits.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && open && hits[active]) { e.preventDefault(); choose(hits[active]) }
    else if (e.key === 'Escape') setOpen(false)
  }
  return (
    <div className="relative min-w-0 flex-1 md:max-w-sm">
      <input
        role="combobox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-activedescendant={open && hits[active] ? `${id}-${hits[active].psgc}` : undefined}
        aria-label="Search barangays"
        autoComplete="off"
        disabled={disabled}
        value={q}
        placeholder="Barangay or PSGC"
        onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKey}
        className="w-full rounded-full border border-line bg-page px-4 py-2 text-sm placeholder:text-muted disabled:opacity-60"
      />
      {open && (
        <ul id={`${id}-list`} role="listbox" aria-label="Matching barangays" className="absolute inset-x-0 top-full z-30 mt-2 max-h-72 overflow-y-auto rounded-xl border border-line bg-chalk p-1 shadow-lg">
          {hits.length === 0 && <li className="px-3 py-2 text-sm text-muted">No barangay matches “{q}”.</li>}
          {hits.map((b, i) => (
            <li key={b.psgc} id={`${id}-${b.psgc}`} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); choose(b) }} onMouseEnter={() => setActive(i)} className={`flex cursor-pointer justify-between gap-3 rounded-lg px-3 py-2 text-sm ${i === active ? 'bg-cobalt-tint' : ''}`}>
              <span>{b.name}</span>
              <span className="font-mono text-xs text-muted">{b.psgc}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
