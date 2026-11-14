const btn = 'grid size-9 place-items-center rounded-full border border-line text-ink disabled:cursor-not-allowed disabled:text-muted disabled:opacity-60'

export default function Timeline() {
  return (
    <div role="group" aria-label="Storm replay coming later" aria-describedby="replay-note" className="pointer-events-auto absolute inset-x-3 bottom-3 z-10 flex items-center gap-3 rounded-full border border-line bg-chalk px-4 py-2 shadow-lg md:inset-x-auto md:left-1/2 md:w-[34rem] md:-translate-x-1/2">
      <div className="flex gap-1.5">
        <button type="button" disabled aria-label="Previous observation" className={btn}>‹</button>
        <button type="button" disabled aria-label="Play replay" className={btn}>▶</button>
        <button type="button" disabled aria-label="Next observation" className={btn}>›</button>
      </div>
      <input type="range" disabled aria-label="Replay position" className="hidden h-1 min-w-0 flex-1 accent-muted opacity-50 md:block" />
      <div id="replay-note" className="min-w-0 leading-tight">
        <p className="text-sm font-medium">Replay · offline</p>
        <p className="truncate text-xs text-muted">Only observed acquisition dates will appear</p>
      </div>
    </div>
  )
}
