import { CloudLightning, Play, X } from 'lucide-react'

// Historical storms that affected Los Baños. Names and dates only; no observation data exists in this build.
const EVENTS = [
  { id: 'kristine-2024', name: 'Severe Tropical Storm Kristine (Trami)', date: 'Oct 2024' },
  { id: 'ulysses-2020', name: 'Typhoon Ulysses (Vamco)', date: 'Nov 2020' },
  { id: 'ondoy-2009', name: 'Tropical Storm Ondoy (Ketsana)', date: 'Sep 2009' },
]

export default function MunicipalityCard({ municipality, onClose }) {
  return (
    <aside aria-label="Storm events" className="pointer-events-auto fixed inset-x-0 bottom-[4.75rem] z-10 flex max-h-[45vh] flex-col overflow-hidden rounded-t-2xl bg-chalk shadow-float md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl">
      <div className="overflow-y-auto p-4">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-cobalt text-white"><CloudLightning aria-hidden size={20} /></span>
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-medium leading-tight">{municipality.name}</h2>
            <p className="text-sm text-muted">Storm events to replay</p>
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
        </div>
        <ul className="mt-3 divide-y divide-line">
          {EVENTS.map((e) => (
            <li key={e.id} className="flex items-center gap-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{e.name}</p>
                <p className="text-muted">{e.date}</p>
              </div>
              <button type="button" disabled title="Replay not available in this build" className="flex items-center gap-1 rounded-lg bg-cobalt-tint px-2 py-1 text-cobalt disabled:opacity-50"><Play aria-hidden size={14} />Replay</button>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted">Replay is not available yet: no storm observations are loaded.</p>
      </div>
    </aside>
  )
}
