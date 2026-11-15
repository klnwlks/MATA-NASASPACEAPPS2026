// Independent sources for the same barangay and pass. Each judges against its own dry-season noise; a source with no
// acquisition near this pass says so instead of reading as "no flood".
const VERDICT = { 1: ['Flood signal', 'bg-cobalt text-white'], 0: ['None seen', 'bg-white/70 text-ink'], null: ['No acquisition', 'bg-white/70 text-muted'] }

export default function SecondOpinions({ evidence, frame }) {
  const sources = Object.entries(evidence ?? {})
  if (!sources.length) return null
  return (
    <>
      <h3 className="mt-3 text-sm font-medium text-cobalt-ink">Second opinions, this pass</h3>
      <ul className="mt-1 divide-y divide-line/70">
        {sources.map(([key, s]) => {
          const [label, tone] = VERDICT[s.flagged[frame] ?? null]
          return (
            <li key={key} className="py-1.5">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium">{s.label}</span>
                <span className={`ml-auto rounded-lg px-2 py-0.5 text-xs font-medium ${tone}`}>{label}</span>
              </div>
            </li>
          )
        })}
      </ul>
    </>
  )
}
