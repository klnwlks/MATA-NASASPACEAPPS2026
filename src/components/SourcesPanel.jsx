import { useEffect } from 'react'
import { Building2, Layers, Mountain, Satellite, Shapes, Trees, Waves, X } from 'lucide-react'
import { SCHEMATIC_HEIGHT_M, TERRAIN_EXAGGERATION } from '../map/style.js'

const rows = [
  [Mountain, 'bg-mint-tint text-mint-ink', 'Elevation · GLO-30', `Copernicus 30 m surface model, smoothed and exaggerated ${TERRAIN_EXAGGERATION}×. Not bare ground or survey-grade.`],
  [Satellite, 'bg-mint-tint text-mint-ink', 'Imagery · Sentinel-2 cloudless', 'EOX 2024 composite, about 10 m per pixel. Shown zoomed out, not a flood observation.'],
  [Building2, 'bg-amber-tint text-amber-ink', 'Buildings · OSM', `OpenStreetMap footprints; missing heights drawn at ${SCHEMATIC_HEIGHT_M} m. Gaps are unknown, not empty.`],
  [Trees, 'bg-mint-tint text-mint-ink', 'Trees · OSM + fill', 'Mapped trees and decorative fill in woods and parks. Shape and size are schematic; shown from zoom 13.'],
  [Shapes, 'bg-cobalt-tint text-cobalt-ink', 'Boundaries · COD-AB', 'NAMRIA and PSA via OCHA, v3 (2025-02-13). Reference lines, not a legal survey.'],
  [Satellite, 'bg-cobalt-tint text-cobalt-ink', 'Floods · Sentinel-1', 'Non-daily radar passes compared with a two-year dry-season reference and a four-year same-month history. Signals are preliminary and not ground-verified; vegetation, buildings and agricultural water can obscure or mimic flooding. Missing observations are unknown, not dry.'],
  [Layers, 'bg-cobalt-tint text-cobalt-ink', 'Second opinions · OPERA, InSAR coherence', 'OPERA water maps and ASF HyP3 InSAR coherence on built-up land (amber) add possible flooding that open-water radar misses. Coherence loss can also come from construction or other change. NISAR (cyan) appears only where its 2026 passes exist.'],
  [Waves, 'bg-cobalt-tint text-cobalt-ink', 'Lake level · DAHITI altimetry', 'Laguna de Bay height roughly every two weeks. Context, not a flood map.'],
]

export default function SourcesPanel({ onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <section role="dialog" aria-label="Data sources" className="absolute right-0 top-full z-30 mt-3 flex max-h-[min(32rem,calc(100dvh-6rem))] w-[min(24rem,calc(100vw-1.5rem))] flex-col rounded-2xl bg-chalk p-4 shadow-float">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium">Where the map comes from</h2>
        <button type="button" aria-label="Close sources" onClick={onClose} className="grid size-8 place-items-center rounded-lg text-muted hover:bg-cobalt-tint hover:text-cobalt"><X aria-hidden size={18} /></button>
      </div>
      <dl tabIndex={0} aria-label="Data source details" className="mt-3 space-y-3 overflow-y-auto overscroll-contain">
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
