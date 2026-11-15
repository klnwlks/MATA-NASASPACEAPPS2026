import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Database, Info, Landmark, Menu, Satellite, X } from 'lucide-react'
import BarangaySearch from './BarangaySearch.jsx'
import SourcesPanel from './SourcesPanel.jsx'
import logoUrl from '../assets/mata-logo.svg'

const item = 'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm font-medium text-ink hover:bg-cobalt-tint'

export default function Navbar({ list, municipalities, floods, boundariesReady, onSelect, onMunicipality, onAbout }) {
  const [panel, setPanel] = useState(null) // null | 'menu' | 'areas' | 'sources'
  const wrap = useRef(null)
  const [areasOpen, setAreasOpen] = useState(false)
  const deskWrap = useRef(null)
  const areasWrap = useRef(null)
  const frames = floods?.frames.length
  const observed = municipalities.filter((m) => floods?.municipalities?.[m.psgc])
  const close = () => setPanel(null)

  useEffect(() => {
    if (!panel) return
    const onKey = (e) => e.key === 'Escape' && close()
    const onDown = (e) => !wrap.current?.contains(e.target) && !deskWrap.current?.contains(e.target) && !areasWrap.current?.contains(e.target) && close()
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onDown)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onDown)
    }
  }, [panel])

  return (
    <header className="pointer-events-auto absolute inset-x-3 top-3 z-20 flex items-center gap-2.5 rounded-2xl bg-chalk p-2 shadow-float">
      <div className="flex shrink-0 items-center gap-2.5">
        <img src={logoUrl} alt="MATA: Tanaw" title="MATA: Tanaw" className="h-10 w-auto object-contain" />
        <h1 className="sr-only">MATA: Tanaw</h1>
      </div>
      <BarangaySearch list={list} municipalities={municipalities} disabled={!boundariesReady} onSelect={onSelect} onMunicipality={onMunicipality} />
      <div className="ml-auto hidden items-center gap-1 md:flex">
        {observed.length > 0 && (
          <div ref={areasWrap} className="relative">
            <button type="button" aria-expanded={panel === 'areas'} aria-haspopup="true" onClick={() => setPanel(panel === 'areas' ? null : 'areas')} className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-cobalt-ink hover:bg-cobalt-tint ${panel === 'areas' ? 'bg-cobalt-tint' : ''}`}>
              <Landmark aria-hidden size={18} />Areas<ChevronDown aria-hidden size={16} className={panel === 'areas' ? 'rotate-180' : ''} />
            </button>
            {panel === 'areas' && (
              <div role="menu" aria-label="Areas with flood data" className="absolute right-0 top-full z-30 mt-3 w-56 rounded-2xl bg-chalk p-2 shadow-float">
                <p className="px-2.5 pb-1 pt-1 text-xs font-medium text-muted">Areas with flood data</p>
                {observed.map((m) => (
                  <button key={m.psgc} role="menuitem" type="button" onClick={() => { close(); onMunicipality(m) }} className={item}>{m.name}</button>
                ))}
              </div>
            )}
          </div>
        )}
        <button type="button" onClick={onAbout} className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-ink hover:bg-cobalt-tint"><Info aria-hidden size={18} />About</button>
        <div ref={deskWrap} className="relative">
          <button type="button" aria-expanded={panel === 'sources'} onClick={() => setPanel(panel ? null : 'sources')} className="flex items-center gap-2 rounded-xl bg-ink px-3.5 py-2 text-sm font-medium text-white hover:bg-cobalt-ink"><Database aria-hidden size={18} />Sources</button>
          {panel === 'sources' && <SourcesPanel onClose={close} />}
        </div>
      </div>
      <div ref={wrap} className="relative shrink-0 md:hidden">
        <button type="button" aria-expanded={panel === 'menu'} aria-haspopup="true" aria-label="Menu" onClick={() => setPanel(panel ? null : 'menu')} className={`grid size-10 place-items-center rounded-xl text-ink hover:bg-cobalt-tint ${panel === 'menu' ? 'bg-cobalt-tint' : ''}`}>
          {panel === 'menu' ? <X aria-hidden size={20} /> : <Menu aria-hidden size={20} />}
        </button>
        {panel === 'menu' && (
          <nav aria-label="Menu" className="absolute right-0 top-full z-30 mt-3 w-[min(18rem,calc(100vw-1.5rem))] rounded-2xl bg-chalk p-2 shadow-float">
            <p className={`mb-1 flex items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] font-medium ${frames ? 'bg-cobalt-tint text-cobalt-ink' : 'bg-coral-tint text-coral-ink'}`}>
              <Satellite aria-hidden size={16} className="shrink-0" />{frames ? `${frames} Sentinel-1 dates observed` : 'No observations loaded'}
            </p>
            {observed.length > 0 && (
              <>
                <button type="button" aria-expanded={areasOpen} onClick={() => setAreasOpen(!areasOpen)} className={item}>
                  <Landmark aria-hidden size={16} className="text-cobalt" />Areas<ChevronDown aria-hidden size={16} className={`ml-auto text-muted ${areasOpen ? 'rotate-180' : ''}`} />
                </button>
                {areasOpen && observed.map((m) => (
                  <button key={m.psgc} type="button" onClick={() => { close(); onMunicipality(m) }} className={`${item} pl-9 font-normal`}>{m.name}</button>
                ))}
                <hr className="my-1.5 border-line" />
              </>
            )}
            <button type="button" onClick={() => { close(); onAbout() }} className={item}><Info aria-hidden size={16} className="text-cobalt" />About</button>
            <button type="button" onClick={() => setPanel('sources')} className={item}><Database aria-hidden size={16} className="text-cobalt" />Sources</button>
          </nav>
        )}
        {panel === 'sources' && <SourcesPanel onClose={close} />}
      </div>
    </header>
  )
}
