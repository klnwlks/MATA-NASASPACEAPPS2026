import { useState } from 'react'
import { List, X } from 'lucide-react'

const HATCH = 'repeating-linear-gradient(135deg, #56607A 0 1.5px, transparent 1.5px 5px)'
const DEPTH = 'linear-gradient(90deg, #299E80, #031A61)' // the two colours the water shader mixes from 0.1 to 2.5 m
const GRID = 'linear-gradient(#789234 0 1px, transparent 1px), linear-gradient(90deg, #789234 0 1px, transparent 1px)'
const SWATCH = 'size-4 shrink-0 rounded-[4px] border'

// Province overview key. Each state differs in fill pattern as well as colour: solid, empty, hatched.
export default function Legend({ coherence }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" aria-label={open ? 'Hide legend' : 'Show legend'} aria-expanded={open} aria-controls="map-legend" onClick={() => setOpen((o) => !o)} className="pointer-events-auto absolute bottom-[7.5rem] right-3 z-20 grid size-11 place-items-center rounded-2xl bg-chalk text-cobalt shadow-float md:hidden">
        {open ? <X aria-hidden size={20} /> : <List aria-hidden size={20} />}
      </button>
      <figure id="map-legend" className={`${open ? 'block' : 'hidden'} pointer-events-auto absolute bottom-[11rem] right-3 z-10 max-h-[calc(100dvh-17rem)] overflow-y-auto rounded-2xl bg-chalk px-3.5 py-2.5 shadow-float md:bottom-auto md:left-3 md:right-auto md:top-20 md:block md:max-h-none md:overflow-visible`}>
        <ul className="space-y-1 text-sm">
          <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-cobalt bg-cobalt/60`} />Flood signal</li>
          <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-cobalt/60 bg-white`} />Below threshold</li>
          <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-muted/60`} style={{ backgroundImage: HATCH }} />Unknown</li>
          {coherence && <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-[#B7791F] bg-[#B7791F]/80`} />Urban flooding · coherence loss</li>}
        </ul>
        <div className="mt-2.5 max-w-44 text-sm">
          <span aria-hidden className="block h-2.5 rounded-[4px]" style={{ backgroundImage: DEPTH }} />
          <span className="mt-0.5 flex justify-between text-[11px] leading-tight text-muted"><span>shallow</span><span>2.5 m+</span></span>
        </div>
        <ul className="mt-2.5 space-y-1 text-sm">
          <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-[#789234]/70 bg-[#CFE08A]`} style={{ backgroundImage: GRID, backgroundSize: '8px 8px' }} />Farmland · OSM</li>
        </ul>
      </figure>
    </>
  )
}
