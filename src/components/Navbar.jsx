import { useState } from 'react'
import { Database, Satellite } from 'lucide-react'
import BarangaySearch from './BarangaySearch.jsx'
import SourcesPanel from './SourcesPanel.jsx'
import logoUrl from '../assets/matatanaw_logo_alt.svg'

export default function Navbar({ list, frames, boundariesReady, onSelect }) {
  const [sources, setSources] = useState(false)
  return (
    <header className="pointer-events-auto absolute inset-x-3 top-3 z-20 flex items-center justify-between gap-3 rounded-2xl bg-chalk px-3 py-2.5 shadow-float md:grid md:grid-cols-[1fr_auto_1fr]">
      <div className="mx-2 flex shrink-0 items-center justify-self-start sm:mx-4">
        <img 
          src={logoUrl} 
          alt="MATA: Tanaw" 
          className="h-10 w-auto object-contain" 
        />
      </div>
      <div className="min-w-0 flex-1 md:w-150 md:flex-initial md:justify-self-center lg:w-96">
        <BarangaySearch list={list} disabled={!boundariesReady} onSelect={onSelect} />
      </div>
      <div className="flex items-center justify-self-end gap-3 sm:gap-5">
        <p className={`hidden items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-[13px] font-medium xl:flex ${frames ? 'bg-cobalt-tint text-cobalt-ink' : 'bg-coral-tint text-coral-ink'}`}>
          <Satellite aria-hidden size={16} />{frames ? `Observations: ${frames} Sentinel-1 dates` : 'Observations: none loaded'}
        </p>
        <div className="relative mr-1 sm:mr-2">
          <button type="button" aria-expanded={sources} onClick={() => setSources((s) => !s)} aria-label="Sources" className="flex items-center gap-2 rounded-xl bg-ink px-3 py-2 text-sm font-medium text-white hover:bg-cobalt-ink sm:px-3.5">
            <Database aria-hidden size={18} /><span className="hidden sm:inline">Sources</span>
          </button>
          {sources && <SourcesPanel onClose={() => setSources(false)} />}
        </div>
      </div>
    </header>
  )
}