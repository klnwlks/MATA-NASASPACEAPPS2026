import { shortDate } from '../data.js'

const HATCH = 'repeating-linear-gradient(135deg, #56607A 0 1.5px, transparent 1.5px 5px)'
const SWATCH = 'size-4 shrink-0 rounded-[4px] border'

// Province overview key. Each state differs in fill pattern as well as colour: solid, empty, hatched.
export default function Legend({ frame }) {
  return (
    <figure className="pointer-events-auto absolute left-[4.75rem] top-36 z-10 rounded-2xl bg-chalk px-3.5 py-2.5 shadow-float md:left-3">
      <figcaption className="text-xs font-medium text-muted">Barangay state{frame ? ` · ${shortDate(frame.utc)}` : ''}</figcaption>
      <ul className="mt-1.5 space-y-1 text-sm">
        <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-cobalt bg-cobalt/60`} />Flood signal</li>
        <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-cobalt/60 bg-white`} />Below threshold</li>
        <li className="flex items-center gap-2"><span aria-hidden className={`${SWATCH} border-muted/60`} style={{ backgroundImage: HATCH }} />Unknown</li>
      </ul>
      <p className="mt-1.5 max-w-44 text-[11px] leading-tight text-muted">Sentinel-1, this pass. Unknown is never drawn as dry.</p>
    </figure>
  )
}
