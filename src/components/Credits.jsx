import { useEffect, useState } from 'react'

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
        <section id="credits-note" className="pointer-events-auto w-[min(22rem,calc(100vw-1.5rem))] rounded-2xl border border-line bg-chalk p-4 shadow-lg">
          <p className="text-sm font-medium">Not an official hazard map</p>
          <p className="mt-2 text-xs text-muted">© OpenStreetMap contributors</p>
          <p className="text-xs text-muted">Contains modified Copernicus DEM GLO-30</p>
          <p className="text-xs text-muted">NAMRIA, PSA via OCHA COD-AB (CC BY-IGO)</p>
        </section>
      )}
      <button
        type="button"
        aria-expanded={open}
        aria-controls="credits-note"
        aria-label={open ? 'Hide disclaimer and credits' : 'Show disclaimer and credits'}
        onClick={() => setOpen((o) => !o)}
        className="pointer-events-auto grid size-10 place-items-center rounded-full border border-line bg-chalk font-mono text-base font-medium shadow-lg hover:bg-cobalt-tint"
      >
        i
      </button>
    </div>
  )
}
