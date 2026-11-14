import { useEffect } from 'react'
import { Building2, Mountain, Shapes, X } from 'lucide-react'
import { SCHEMATIC_HEIGHT_M, TERRAIN_EXAGGERATION } from '../map/style.js'

const rows = [
  [Mountain, 'bg-mint-tint text-mint-ink', 'Elevation · GLO-30', `Copernicus 30 m surface model, smoothed. Not bare ground, not survey-grade. Drawn ${TERRAIN_EXAGGERATION}× taller than real.`],
  [Building2, 'bg-amber-tint text-amber-ink', 'Buildings · OSM', `Footprints from OpenStreetMap. Where height is missing, drawn at ${SCHEMATIC_HEIGHT_M} m. Gaps mean unknown, not empty.`],
  [Shapes, 'bg-cobalt-tint text-cobalt-ink', 'Boundaries · COD-AB', 'NAMRIA and PSA, via OCHA, version 3 of 2025-02-13. Reference lines, not a legal survey.'],
]

export default function SourcesPanel({ onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <section role="dialog" aria-label="Data sources" className="absolute right-0 top-full z-30 mt-3 w-[min(24rem,calc(100vw-1.5rem))] rounded-2xl bg-chalk p-4 shadow-float">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium">Where the map comes from</h2>
        <button type="button" aria-label="Close sources" onClick={onClose} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
      </div>
      <dl className="mt-3 space-y-3">
        {rows.map(([Icon, tone, name, note]) => (
          <div key={name} className="flex gap-3">
            <span className={`grid size-9 shrink-0 place-items-center rounded-xl ${tone}`}><Icon aria-hidden size={18} /></span>
            <div>
              <dt className="text-sm font-medium">{name}</dt>
              <dd className="text-sm text-muted">{note}</dd>
            </div>
          </div>
        ))}
      </dl>
    </section>
  )
}
