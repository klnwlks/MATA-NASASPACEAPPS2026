import { useEffect } from 'react'
import { Building2, Layers, Mountain, Satellite, Shapes, Trees, Waves, X } from 'lucide-react'
import { SCHEMATIC_HEIGHT_M, TERRAIN_EXAGGERATION } from '../map/style.js'

const rows = [
  [Mountain, 'bg-mint-tint text-mint-ink', 'Elevation · GLO-30', `Copernicus 30 m surface model, smoothed. Not bare ground, not survey-grade. Drawn ${TERRAIN_EXAGGERATION}× taller than real.`],
  [Satellite, 'bg-mint-tint text-mint-ink', 'Imagery · Sentinel-2 cloudless', 'EOX 2024 composite, about 10 m per pixel, shown only when zoomed out. Not storm-date imagery and not a flood observation.'],
  [Building2, 'bg-amber-tint text-amber-ink', 'Buildings · OSM', `Footprints from OpenStreetMap. Where height is missing, drawn at ${SCHEMATIC_HEIGHT_M} m. Gaps mean unknown, not empty.`],
  [Trees, 'bg-mint-tint text-mint-ink', 'Trees · OSM + fill', 'Trees mapped in OpenStreetMap are drawn as mapped. The rest are decorative fill scattered inside mapped woods and parks, not observed trees. Shape and size are schematic. Drawn only for the municipality in view, from zoom 13.'],
  [Shapes, 'bg-cobalt-tint text-cobalt-ink', 'Boundaries · COD-AB', 'NAMRIA and PSA via OCHA, version 3 of 2025-02-13. National admin-2 areas include Metro Manila districts; the detailed Laguna view has 682 barangays. Reference lines, not a legal survey.'],
  [Satellite, 'bg-cobalt-tint text-cobalt-ink', 'Floods · Sentinel-1', 'Radar passes are not daily. The current processing uses a dry-season reference from the same track within the two-year replay window. Buildings and tree cover can hide floodwater; paddies may look like water. A missing observation is unknown, not dry.'],
  [Layers, 'bg-cobalt-tint text-cobalt-ink', 'Second opinions · deferred', 'OPERA, NISAR and InSAR coherence are not part of the current primary-source processing run.'],
  [Waves, 'bg-cobalt-tint text-cobalt-ink', 'Lake level · DAHITI altimetry', 'Laguna de Bay surface height every 2 weeks or so. Context for lakeshore flooding, not a flood map.'],
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
