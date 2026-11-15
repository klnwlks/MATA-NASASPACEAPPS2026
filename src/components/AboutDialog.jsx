import { useEffect, useRef } from 'react'
import { ArrowRight, X } from 'lucide-react'
import logoUrl from '../assets/mata-logo.svg'

const HATCH = 'repeating-linear-gradient(135deg, #56607A 0 1.5px, transparent 1.5px 5px)'
const SWATCH = 'mt-0.5 size-4 shrink-0 rounded-[4px] border'

const KEY = [
  ['border-cobalt bg-cobalt/60', null, 'Flood signal', 'Radar saw open water on this pass.', 'Radar saw open water.'],
  ['border-cobalt/60 bg-white', null, 'None seen', 'Radar looked and saw no flood water.', 'Radar saw no flood water.'],
  ['border-[#B7791F] bg-[#B7791F]/80', null, 'Coherence loss', 'Marks possible urban flooding: built-up radar returns stopped matching an earlier pass.', 'Possible urban flooding.'],
  ['border-muted/60', HATCH, 'Unknown', 'No view: no pass, steep ground, or built-up and tree cover. Never drawn as dry.', 'No view. Never drawn as dry.'],
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
      <div className="p-5 sm:p-8">
        <div className="flex items-center gap-3.5">
          <img src={logoUrl} alt="" aria-hidden className="h-11 w-auto shrink-0 object-contain" />
          <h2 id="about-title" className="min-w-0 flex-1 text-2xl font-medium tracking-[-0.02em]">MATA: Tanaw</h2>
          <button type="button" aria-label="Close about" onClick={() => dialog.current.close()} className="-mr-2 grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
        </div>

        <p className="mt-4 max-w-[60ch] text-pretty text-sm leading-relaxed sm:mt-6 sm:text-base">
          <span className="sm:hidden">MATA: Tanaw uses Sentinel-1 radar to replay how typhoon floods spread and receded in Philippine river basins, and how long each barangay stayed underwater. It helps LGUs and DRRM offices prioritize drainage, evacuation, and recovery.</span>
          <span className="hidden sm:inline">MATA: Tanaw (Mapping A Typhoon Aftermath: Tracking Affected Neighborhoods Across Waters) is a SAR-based decision-support web app. Using multi-temporal Sentinel-1 backscatter change detection, it replays how typhoon floods spread and receded in Philippine river basins and maps how long each barangay stayed underwater, with uncertainty ranges. Exposure indices and resident photo validation help LGUs and DRRM offices prioritize drainage, evacuation, and recovery.</span>
        </p>

        <div className="mt-4 rounded-xl bg-cobalt-tint px-4 py-3 text-sm leading-relaxed text-cobalt-ink sm:mt-6">
          <p>{passes ? `${passes} observed Sentinel-1 passes. ` : 'No observations loaded. '}{(floods?.coverageNote ?? 'Focus: Bay, Pila, Victoria, Santa Cruz').replace(/\.?$/, '.')} Pins with a halo have flood records.<span className="hidden sm:inline"> The rest are not mapped yet. Flood durations, exposure indices and photo validation are still to come.</span></p>
        </div>

        <ul className="mt-4 space-y-2 border-t border-line pt-4 sm:mt-6 sm:space-y-2.5 sm:pt-6">
          {KEY.map(([cls, bg, name, note, short]) => (
            <li key={name} className="flex gap-3 text-sm">
              <span aria-hidden className={`${SWATCH} ${cls}`} style={bg ? { backgroundImage: bg } : undefined} />
              <p className="text-muted"><span className="font-medium text-ink">{name}.</span> <span className="sm:hidden">{short}</span><span className="hidden sm:inline">{note}</span></p>
            </li>
          ))}
        </ul>

        <p className="mt-4 hidden border-t border-line pt-6 text-sm leading-relaxed text-muted sm:mt-6 sm:block">
          Built by Team Masasarap in Manila for the NASA Space Apps challenge “Dancing with the SARs”: {TEAM.slice(0, -1).join(', ')} and {TEAM.at(-1)}.
        </p>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3 sm:mt-6">
          <p className="text-xs text-muted">Passes are not daily and can miss floods. Not an official hazard map.</p>
          <button type="button" data-primary onClick={() => dialog.current.close()} className="flex items-center gap-2 rounded-xl bg-cobalt px-4 py-2.5 text-sm font-medium text-white hover:bg-cobalt-ink">
            Explore the map <ArrowRight aria-hidden size={16} />
          </button>
        </div>
      </div>
    </dialog>
  )
}
