export default function FloodMunicipalityPicker({ municipalities, floods, selected, onSelect }) {
  const available = municipalities.filter((m) => floods?.municipalities?.[m.psgc])
  return (
    <label className="flex min-w-0 items-center gap-2 text-sm text-muted">
      <span className="sr-only">Municipality with flood observations</span>
      <select
        aria-label="Municipality with flood observations"
        value={available.some((m) => m.psgc === selected) ? selected : ''}
        disabled={!available.length}
        onChange={(event) => {
          const municipality = available.find((m) => m.psgc === event.target.value)
          if (municipality) onSelect(municipality)
        }}
        className="max-w-36 rounded-xl bg-cobalt-tint px-3 py-2 text-sm font-medium text-cobalt-ink disabled:opacity-60 sm:max-w-48"
      >
        <option value="">Flood observations</option>
        {available.map((m) => <option key={m.psgc} value={m.psgc}>{m.name}</option>)}
      </select>
    </label>
  )
}
