import { useEffect, useState } from 'react'
import background from '../assets/loading-bg.svg'
import logo from '../assets/mata-logo.svg'

const steps = [
  ['boundaries', 'Drawing Laguna’s municipal and barangay boundaries.'],
  ['floods', 'Preparing observed Sentinel-1 passes.'],
  ['basemap', 'Gathering roads, buildings, and map tiles.'],
  ['terrain', 'Bringing the landscape into view.'],
]

export default function LoadingScreen({ status, onDone }) {
  const [dismissed, setDismissed] = useState(false)
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 10000)
    return () => clearTimeout(timer)
  }, [])
  const complete = steps.filter(([key]) => status[key] !== 'loading').length
  const ready = complete === steps.length || status.webgl === 'failed'
  const done = dismissed || ready
  useEffect(() => {
    if (done) onDone()
  }, [done, onDone])
  if (done) return null
  const message = steps.find(([key]) => status[key] === 'loading')?.[1]
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center overflow-hidden bg-[#e9ebf2] px-6 text-center" role="status" aria-live="polite">
      <img src={background} alt="" aria-hidden="true" className="pointer-events-none absolute inset-0 size-full object-cover" />
      <div className="relative flex w-full max-w-xl flex-col items-center">
        <img src={logo} alt="MATA: Tanaw" className="w-[min(88vw,40rem)]" />
        <div className="mt-6 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-[#d5d9e5]" role="progressbar" aria-label="Loading map and data" aria-valuemin={0} aria-valuemax={4} aria-valuenow={complete}>
          <div className="h-full rounded-full bg-cobalt transition-[width] duration-500" style={{ width: `${complete * 25}%` }} />
        </div>
        <p className="mt-4 min-h-10 text-sm text-muted">{message}</p>
        {slow && <button type="button" onClick={() => setDismissed(true)} className="mt-3 rounded-lg px-3 py-2 text-sm font-medium text-cobalt-ink underline underline-offset-4">Continue to map while loading</button>}
      </div>
    </div>
  )
}
