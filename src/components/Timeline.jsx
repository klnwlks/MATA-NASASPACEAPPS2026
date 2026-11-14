import { ChevronDown, CloudLightning, Play, SkipBack, SkipForward } from 'lucide-react'

const btn = 'grid size-9 place-items-center rounded-xl bg-page text-ink disabled:cursor-not-allowed disabled:text-muted disabled:opacity-60'

export default function Timeline() {
  return (
    <div role="group" aria-label="Storm replay coming later" aria-describedby="replay-note" className="pointer-events-auto absolute inset-x-3 bottom-3 z-10 flex items-center gap-3 rounded-2xl bg-chalk p-2.5 shadow-float md:inset-x-auto md:left-1/2 md:w-[46rem] md:-translate-x-1/2">
      <div className="relative min-w-0 flex-1 md:w-52 md:flex-none">
        <CloudLightning aria-hidden size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-coral-ink" />
        <select disabled aria-label="Storm event" className="w-full appearance-none rounded-xl bg-coral-tint py-2 pl-10 pr-9 text-sm font-medium text-coral-ink disabled:cursor-not-allowed disabled:opacity-70">
          <option>No storm loaded</option>
        </select>
        <ChevronDown aria-hidden size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-coral-ink" />
      </div>
      <div className="flex gap-1.5">
        <button type="button" disabled aria-label="Previous observation" className={btn}><SkipBack aria-hidden size={18} /></button>
        <button type="button" disabled aria-label="Play replay" className={btn}><Play aria-hidden size={18} /></button>
        <button type="button" disabled aria-label="Next observation" className={btn}><SkipForward aria-hidden size={18} /></button>
      </div>
      <input type="range" disabled aria-label="Replay position" className="hidden h-1 min-w-0 flex-1 accent-muted opacity-50 md:block" />
      <div id="replay-note" className="hidden leading-tight lg:block">
        <p className="whitespace-nowrap text-sm font-medium">Replay · offline</p>
        <p className="max-w-40 text-xs text-muted">Only observed acquisition dates will appear</p>
      </div>
      <p className="sr-only lg:hidden">Replay · offline. Only observed acquisition dates will appear.</p>
    </div>
  )
}
