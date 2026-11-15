import { useState } from 'react'
import { Database, Info, ScanEye, Satellite } from 'lucide-react'
import BarangaySearch from './BarangaySearch.jsx'
import SourcesPanel from './SourcesPanel.jsx'

export default function Navbar({ list, municipalities, frames, boundariesReady, onSelect, onMunicipality, onAbout, picker }) {
  const [sources, setSources] = useState(false)
  return (
    <header className="pointer-events-auto absolute inset-x-3 top-3 z-20 flex items-center gap-3 rounded-2xl bg-chalk px-3 py-2.5 shadow-float">
      <div className="flex items-center gap-2.5">
        <span className="grid size-9 place-items-center rounded-xl bg-cobalt text-white"><ScanEye aria-hidden size={20} /></span>
        <h1 className="whitespace-nowrap text-lg font-medium"><span className="hidden sm:inline">MATA: Tanaw</span><span className="sm:hidden">MATA</span></h1>
      </div>
      <BarangaySearch list={list} municipalities={municipalities} disabled={!boundariesReady} onSelect={onSelect} onMunicipality={onMunicipality} />
      <div className="absolute right-0 top-full mt-2 sm:static sm:mt-0">{picker}</div>
      <p className={`ml-auto hidden items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-[13px] font-medium lg:flex ${frames ? 'bg-cobalt-tint text-cobalt-ink' : 'bg-coral-tint text-coral-ink'}`}>
        <Satellite aria-hidden size={16} />{frames ? `Observations: ${frames} Sentinel-1 dates` : 'Observations: none loaded'}
      </p>
      <button type="button" aria-label="About MATA: Tanaw" onClick={() => { setSources(false); onAbout() }} className="flex items-center gap-2 rounded-xl px-2 py-2 text-sm font-medium text-ink hover:bg-cobalt-tint sm:px-3">
        <Info aria-hidden size={18} /><span className="hidden sm:inline">About</span>
      </button>
      <div className="relative">
        <button type="button" aria-expanded={sources} onClick={() => setSources((s) => !s)} aria-label="Sources" className="flex items-center gap-2 rounded-xl bg-ink px-3 py-2 text-sm font-medium text-white hover:bg-cobalt-ink sm:px-3.5">
          <Database aria-hidden size={18} /><span className="hidden sm:inline">Sources</span>
        </button>
        {sources && <SourcesPanel onClose={() => setSources(false)} />}
      </div>
    </header>
  )
}
