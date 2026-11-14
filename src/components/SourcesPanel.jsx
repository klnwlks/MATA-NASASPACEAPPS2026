import { useEffect } from 'react'
import { SCHEMATIC_HEIGHT_M, TERRAIN_EXAGGERATION } from '../map/style.js'

const rows = [
  ['Elevation · GLO-30', `Copernicus 30 m surface model, smoothed. Not bare ground, not survey-grade. Drawn ${TERRAIN_EXAGGERATION}× taller than real.`],
  ['Buildings · OSM', `Footprints from OpenStreetMap. Where height is missing, drawn at ${SCHEMATIC_HEIGHT_M} m. Gaps mean unknown, not empty.`],
  ['Boundaries · COD-AB', 'NAMRIA and PSA, via OCHA, version 3 of 2025-02-13. Reference lines, not a legal survey.'],
]

export default function SourcesPanel({ onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <section role="dialog" aria-label="Data sources" className="absolute right-0 top-full z-30 mt-3 w-[min(24rem,calc(100vw-2rem))] rounded-2xl border border-line bg-chalk p-4 shadow-lg">
      <dl className="space-y-3">
        {rows.map(([name, note]) => (
          <div key={name}>
            <dt className="text-sm font-medium">{name}</dt>
            <dd className="text-sm text-muted">{note}</dd>
          </div>
        ))}
      </dl>
      <button type="button" onClick={onClose} className="mt-4 rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-cobalt-tint">Close</button>
    </section>
  )
}
