import { useEffect, useState } from 'react'
import { Info, ShieldAlert, X } from 'lucide-react'

export default function Credits() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])
  return (
    <div className="pointer-events-none absolute bottom-[4.75rem] right-3 z-20 flex flex-col items-end gap-2 md:bottom-3">
      {open && (
        <section id="credits-note" className="pointer-events-auto w-[min(22rem,calc(100vw-1.5rem))] rounded-2xl bg-chalk p-4 shadow-float">
          <p className="flex items-center gap-2 text-sm font-medium"><span className="grid size-8 place-items-center rounded-lg bg-amber-tint text-amber-ink"><ShieldAlert aria-hidden size={17} /></span>Not an official hazard map</p>
          <p className="mt-2 text-xs text-muted">© OpenStreetMap contributors</p>
          <p className="text-xs text-muted">Contains modified Copernicus DEM GLO-30</p>
          <p className="text-xs text-muted">Sentinel-2 cloudless 2024 by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2024), CC BY-NC-SA 4.0</p>
          <p className="text-xs text-muted">NAMRIA, PSA via OCHA COD-AB (CC BY-IGO)</p>
          <p className="text-xs text-muted">Contains modified Copernicus Sentinel-1 data 2024–2026, RTC via Microsoft Planetary Computer</p>
          <p className="text-xs text-muted">© ESA WorldCover project 2021, CC BY 4.0</p>
        </section>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-controls="credits-note"
        aria-label={open ? 'Hide disclaimer and credits' : 'Show disclaimer and credits'}
        onClick={() => setOpen((o) => !o)}
        className="pointer-events-auto grid size-10 place-items-center rounded-xl bg-chalk text-cobalt shadow-float hover:bg-cobalt-tint"
      >
        {open ? <X aria-hidden size={19} /> : <Info aria-hidden size={19} />}
      </button>
    </div>
  )
}
