// Laguna de Bay surface height from altimetry, on the same time axis as the passes. Each pass is a tick on the base
// line, so the 6- and 12-day spacing stays visible; the lake line joins real altimetry points only.
const W = 300
const H = 64
const PAD = { l: 4, r: 4, t: 6, b: 12 }
const NEAR_DAYS = 8
const DAY = 86400000

export default function LakeChart({ lake, frames, frame }) {
  if (!lake?.points.length || !frames.length) return null
  const t0 = Date.parse(frames[0].utc)
  const t1 = Date.parse(frames.at(-1).utc)
  const pts = lake.points.filter((p) => Date.parse(p.utc) >= t0 - 20 * DAY && Date.parse(p.utc) <= t1 + 20 * DAY)
  const lo = Math.min(...pts.map((p) => p.m)) - 0.2
  const hi = Math.max(...pts.map((p) => p.m)) + 0.2
  const x = (t) => PAD.l + ((t - t0) / (t1 - t0)) * (W - PAD.l - PAD.r)
  const y = (m) => PAD.t + (1 - (m - lo) / (hi - lo)) * (H - PAD.t - PAD.b)
  const now = Date.parse(frames[frame].utc)
  const near = pts.reduce((best, p) => (Math.abs(Date.parse(p.utc) - now) < Math.abs(Date.parse(best.utc) - now) ? p : best), pts[0])
  const gapDays = Math.round(Math.abs(Date.parse(near.utc) - now) / DAY)
  const label = gapDays <= NEAR_DAYS ? `${near.m.toFixed(2)} m · ${gapDays ? `${gapDays} d from pass` : 'same day'}` : `no altimetry within ${NEAR_DAYS} d`
  const clip = (p) => Math.min(Math.max(x(Date.parse(p.utc)), PAD.l), W - PAD.r)
  return (
    <figure className="pointer-events-auto absolute bottom-[4.75rem] left-1/2 z-10 hidden w-[34rem] -translate-x-1/2 items-center gap-3 rounded-2xl bg-chalk px-3 py-2 shadow-float xl:flex">
      <figcaption className="w-40 shrink-0 leading-tight">
        <p className="text-sm font-medium">Laguna de Bay level</p>
        <p className="font-mono text-xs text-muted">{label}</p>
        <p className="text-[11px] text-muted">Altimetry, DAHITI. Context, not a flood map.</p>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-16 min-w-0 flex-1" role="img" aria-label={`Lake surface height from ${lo.toFixed(1)} to ${hi.toFixed(1)} metres over the replay period. Nearest reading to this pass: ${label}.`}>
        <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b + 4} y2={H - PAD.b + 4} stroke="#DDE1EA" />
        {frames.map((f) => (
          <line key={f.utc} x1={x(Date.parse(f.utc))} x2={x(Date.parse(f.utc))} y1={H - PAD.b + 1} y2={H - PAD.b + 7} stroke="#56607A" strokeWidth="0.6" />
        ))}
        <polyline fill="none" stroke="#0E9DB8" strokeWidth="1.6" strokeLinejoin="round" points={pts.map((p) => `${clip(p)},${y(p.m)}`).join(' ')} />
        {pts.map((p) => <circle key={p.utc} cx={clip(p)} cy={y(p.m)} r="1.6" fill="#0E9DB8" />)}
        <line x1={x(now)} x2={x(now)} y1={PAD.t - 4} y2={H - PAD.b + 8} stroke="#1F4FD8" strokeWidth="1.5" />
      </svg>
    </figure>
  )
}
