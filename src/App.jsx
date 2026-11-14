import { useCallback, useEffect, useMemo, useState } from 'react'
import MapStage from './map/MapStage.jsx'
import Navbar from './components/Navbar.jsx'
import BarangayCard from './components/BarangayCard.jsx'
import MapControls from './components/MapControls.jsx'
import Timeline from './components/Timeline.jsx'
import Status from './components/Status.jsx'
import Credits from './components/Credits.jsx'
import { loadBarangays } from './data.js'
import { manilaTime } from './map/sun.js'

export default function App() {
  const [barangays, setBarangays] = useState(null)
  const [status, setStatus] = useState({ terrain: 'loading', basemap: 'loading', boundaries: 'loading' })
  const [map, setMap] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [show, setShow] = useState({ boundaries: true, buildings: true })
  const [fit, setFit] = useState(null)
  const [homeTick, setHomeTick] = useState(0)
  const [minutes, setMinutes] = useState(15 * 60 + 30) // Manila clock; mid-afternoon reads best by default
  const time = useMemo(() => manilaTime(minutes), [minutes])

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

  const select = useCallback(
    (id, locate) => {
      setSelectedId(id)
      const b = barangays?.list.find((x) => x.psgc === id)
      if (locate && b) setFit({ bounds: b.bounds })
    },
    [barangays],
  )

  return (
    <div className="relative h-full overflow-hidden">
      <div className="absolute inset-0">
        <MapStage barangays={barangays} selectedId={selectedId} show={show} fit={fit} homeTick={homeTick} time={time} onSelect={select} onStatus={report} onMap={setMap} />
        <Navbar list={barangays?.list ?? []} boundariesReady={!!barangays} onSelect={select} />
        <Status status={status} />
        {barangays && <BarangayCard list={barangays.list} selectedId={selectedId} onClose={() => setSelectedId(null)} onLocate={(b) => setFit({ bounds: b.bounds })} />}
        <MapControls map={map} show={show} onShow={setShow} onHome={() => setHomeTick((t) => t + 1)} minutes={minutes} onMinutes={setMinutes} />
        <Timeline />
        <Credits />
      </div>
    </div>
  )
}
