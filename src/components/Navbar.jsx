import { useState } from 'react'
import BarangaySearch from './BarangaySearch.jsx'
import SourcesPanel from './SourcesPanel.jsx'

export default function Navbar({ list, boundariesReady, onSelect }) {
  const [sources, setSources] = useState(false)
  return (
    <header className="pointer-events-auto absolute inset-x-3 top-3 z-20 flex items-center gap-3 rounded-2xl border border-line bg-chalk px-4 py-2.5 shadow-lg">
      <h1 className="whitespace-nowrap text-lg font-medium">MATA<span className="hidden sm:inline">: Tanaw</span></h1>
      <BarangaySearch list={list} disabled={!boundariesReady} onSelect={onSelect} />
      <p className="ml-auto hidden whitespace-nowrap rounded-full bg-cobalt-tint px-3 py-1 text-[13px] font-medium text-cobalt-ink lg:block">Observations: none loaded</p>
      <div className="relative">
        <button type="button" aria-expanded={sources} onClick={() => setSources((s) => !s)} className="rounded-full border border-line px-3.5 py-1.5 text-sm font-medium hover:bg-cobalt-tint">Sources</button>
        {sources && <SourcesPanel onClose={() => setSources(false)} />}
      </div>
    </header>
  )
}
