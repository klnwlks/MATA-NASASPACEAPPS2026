import { useEffect, useRef } from 'react'
import { ArrowRight, ScanEye, X } from 'lucide-react'

const HATCH = 'repeating-linear-gradient(135deg, #56607A 0 1.5px, transparent 1.5px 5px)'
const SWATCH = 'mt-0.5 size-4 shrink-0 rounded-[4px] border'

const KEY = [
  ['border-cobalt bg-cobalt/60', null, 'Flood signal', 'Radar saw open water on this pass.'],
  ['border-cobalt/60 bg-white', null, 'None seen', 'Radar looked and saw no flood water.'],
  ['border-muted/60', HATCH, 'Unknown', 'No view: no pass, steep ground, or built-up and tree cover. Never drawn as dry.'],
]

const TEAM = ['Lukas Bebis', 'Angelica Saavedra', 'Jed Cabacang', 'Dave Caidic', 'Jericon Esguerra', 'Anthony Espina']

// The first thing a visitor reads after the loading screen, and the About button's content. Plain language, with the
// limits of the record stated before anything is claimed.
export default function AboutDialog({ onClose, floods }) {
  const dialog = useRef(null)
  useEffect(() => {
    dialog.current.showModal()
    dialog.current.querySelector('[data-primary]').focus()
  }, [])
  const passes = floods?.frames.length

  return (
    <dialog ref={dialog} onClose={onClose} aria-labelledby="about-title" className="about-dialog m-auto max-h-[calc(100dvh-2rem)] w-[min(36rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl bg-chalk p-0 text-ink shadow-float backdrop:bg-ink/55">
      <div className="p-6 sm:p-8">
        <div className="flex items-center gap-3.5">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-cobalt text-white"><ScanEye aria-hidden size={24} /></span>
          <h2 id="about-title" className="min-w-0 flex-1 text-2xl font-medium tracking-[-0.02em]">MATA: Tanaw</h2>
          <button type="button" aria-label="Close about" onClick={() => dialog.current.close()} className="-mr-2 grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
        </div>

        <p className="mt-6 max-w-[60ch] text-pretty text-base leading-relaxed">
          MATA: Tanaw (Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters) is a SAR-based decision-support web app. Using multi-temporal Sentinel-1 backscatter change detection, it replays how typhoon floods spread and receded in Philippine river basins and maps how long each barangay stayed underwater, with uncertainty ranges. Exposure indices and resident photo validation help LGUs and DRRM offices prioritize drainage, evacuation, and recovery.
        </p>

        <div className="mt-6 rounded-xl bg-cobalt-tint px-4 py-3 text-sm leading-relaxed text-cobalt-ink">
          <p className="font-medium">{passes ? `Today: ${passes} observed Sentinel-1 passes` : 'Today: no observations loaded'}</p>
          <p className="mt-0.5">{(floods?.coverageNote ?? 'Focus: Bay, Pila, Victoria, Santa Cruz').replace(/\.?$/, '.')} Pins with a halo have flood records; the rest are not mapped yet. Flood durations, exposure indices and photo validation are still to come.</p>
        </div>

        <ul className="mt-6 space-y-2.5 border-t border-line pt-6">
          {KEY.map(([cls, bg, name, note]) => (
            <li key={name} className="flex gap-3 text-sm">
              <span aria-hidden className={`${SWATCH} ${cls}`} style={bg ? { backgroundImage: bg } : undefined} />
              <p className="text-muted"><span className="font-medium text-ink">{name}.</span> {note}</p>
            </li>
          ))}
        </ul>

        <p className="mt-6 border-t border-line pt-6 text-sm leading-relaxed text-muted">
          Built by Team Masasarap in Manila for the NASA Space Apps challenge “Dancing with the SARs”: {TEAM.slice(0, -1).join(', ')} and {TEAM.at(-1)}.
        </p>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <p className="text-xs text-muted">Passes are not daily and can miss floods. Not an official hazard map.</p>
          <button type="button" data-primary onClick={() => dialog.current.close()} className="flex items-center gap-2 rounded-xl bg-cobalt px-4 py-2.5 text-sm font-medium text-white hover:bg-cobalt-ink">
            Explore the map <ArrowRight aria-hidden size={16} />
          </button>
        </div>
      </div>
    </dialog>
  )
}
