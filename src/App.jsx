import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import MapStage from './map/MapStage.jsx'
import Navbar from './components/Navbar.jsx'
import BarangayCard from './components/BarangayCard.jsx'
import MapControls from './components/MapControls.jsx'
import MunicipalityCard from './components/MunicipalityCard.jsx'
import Timeline from './components/Timeline.jsx'
import Status from './components/Status.jsx'
import Credits from './components/Credits.jsx'
import LakeChart from './components/LakeChart.jsx'
import { loadBarangays, loadFloods } from './data.js'
import { manilaMinutes, manilaTime } from './map/sun.js'

const SWEEP_MS = 4000

export default function App() {
  const [barangays, setBarangays] = useState(null)
  const [floods, setFloods] = useState(null)
  const [frame, setFrame] = useState(0)
  const [status, setStatus] = useState({ terrain: 'loading', basemap: 'loading', boundaries: 'loading', floods: 'loading' })
  const [map, setMap] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [municipality, setMunicipality] = useState(null)
  const [show, setShow] = useState({ boundaries: true, buildings: true, coherence: true, nisar: true })
  const [fit, setFit] = useState(null)
  const [homeTick, setHomeTick] = useState(0)
  const [clockOverride, setClockOverride] = useState(null) // Manila minutes the user dialled in; null follows the satellite pass
  const passUtc = floods?.frames[frame]?.utc
  const pass = useMemo(() => (passUtc ? new Date(passUtc) : null), [passUtc])
  const [sweep, setSweep] = useState(null)
  const lastPass = useRef(null)
  // Every pass is at the same clock time, so moving to a new pass plays one 24 h sun cycle ending at that pass.
  useEffect(() => {
    const prev = lastPass.current
    lastPass.current = pass
    if (!pass || !prev || prev.getTime() === pass.getTime() || clockOverride != null) return
    const end = pass.getTime()
    const t0 = performance.now()
    let raf
    const step = (now) => {
      const k = Math.min(1, (now - t0) / SWEEP_MS)
      setSweep(k < 1 ? new Date(end - (1 - k) * 864e5) : null)
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => {
      cancelAnimationFrame(raf)
      setSweep(null)
    }
  }, [pass, clockOverride])
  const time = useMemo(() => sweep ?? (clockOverride == null ? (pass ?? manilaTime(15 * 60 + 30)) : manilaTime(clockOverride, pass ?? new Date())), [sweep, clockOverride, pass])
  const minutes = manilaMinutes(time)

  const report = useCallback((key, value) => setStatus((s) => (s[key] === value ? s : { ...s, [key]: value })), [])

  useEffect(() => {
    loadBarangays().then(
      (data) => {
        setBarangays(data)
        report('boundaries', 'ok')
      },
      () => report('boundaries', 'failed'),
    )
  }, [report])

  useEffect(() => {
    loadFloods().then(
      (data) => {
        setFloods(data)
        report('floods', 'ok')
      },
      () => report('floods', 'failed'),
    )
  }, [report])

  const select = useCallback(
    (id, locate) => {
      setSelectedId(id)
      setMunicipality(null)
      const b = barangays?.list.find((x) => x.psgc === id)
      if (locate && b) setFit({ bounds: b.bounds })
    },
    [barangays],
  )

  const openMunicipality = useCallback((m) => {
    setSelectedId(null)
    setMunicipality(m)
    setFit({ bounds: m.bounds })
  }, [])

  return (
    <div className="relative h-full overflow-hidden">
      <div className="absolute inset-0">
        <MapStage barangays={barangays} floods={floods} frame={frame} selectedId={selectedId} show={show} fit={fit} homeTick={homeTick} time={time} onSelect={select} onMunicipality={openMunicipality} onStatus={report} onMap={setMap} />
        <Navbar list={barangays?.list ?? []} frames={floods?.frames.length} boundariesReady={!!barangays} onSelect={select} />
        <Status status={status} />
        {barangays && <BarangayCard list={barangays.list} floods={floods} frame={frame} selectedId={selectedId} onClose={() => setSelectedId(null)} onLocate={(b) => setFit({ bounds: b.bounds })} onFrame={setFrame} />}
        {municipality && <MunicipalityCard municipality={municipality} floods={floods} onFrame={setFrame} onClose={() => setMunicipality(null)} />}
        <MapControls map={map} show={show} onShow={setShow} onHome={() => setHomeTick((t) => t + 1)} minutes={minutes} onMinutes={setClockOverride} followingPass={clockOverride == null && !!pass} onFollowPass={pass ? () => setClockOverride(null) : null} />
        <LakeChart lake={floods?.lake} frames={floods?.frames ?? []} frame={frame} />
        <Timeline floods={floods} frame={frame} onFrame={setFrame} />
        <Credits />
      </div>
    </div>
  )
}
