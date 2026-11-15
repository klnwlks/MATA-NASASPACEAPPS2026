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
import Legend from './components/Legend.jsx'
import { loadBarangays, loadFloods, loadMunicipality } from './data.js'
import { manilaMinutes, manilaTime } from './map/sun.js'

export default function App() {
  const [barangays, setBarangays] = useState(null)
  const [floods, setFloods] = useState(null)
  const [frame, setFrame] = useState(0)
  const [status, setStatus] = useState({ terrain: 'loading', basemap: 'loading', boundaries: 'loading', floods: 'loading' })
  const [map, setMap] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [municipality, setMunicipality] = useState(null)
  const [province, setProvince] = useState(null)
  const [provinces, setProvinces] = useState([])
  const [focusId, setFocusId] = useState(null) // the municipality the 3D layers belong to: under the screen centre when zoomed in
  const [manifests, setManifests] = useState({}) // munipsgc -> { status: 'loading' | 'ok' | 'failed', data }
  const requested = useRef(new Set())
  const [show, setShow] = useState({ boundaries: true, buildings: true, coherence: true, nisar: true })
  const [fit, setFit] = useState(null)
  const [homeTick, setHomeTick] = useState(0)
  const [clockOverride, setClockOverride] = useState(null) // Manila minutes the user dialled in; null follows the satellite pass
  const passUtc = floods?.frames[frame]?.utc
  const pass = useMemo(() => (passUtc ? new Date(passUtc) : null), [passUtc])
  const time = useMemo(() => (clockOverride == null ? (pass ?? manilaTime(15 * 60 + 30)) : manilaTime(clockOverride, pass ?? new Date())), [clockOverride, pass])
  const minutes = manilaMinutes(time)


  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/provinces.geojson`)
      .then((res) => { if (!res.ok) throw new Error(`provinces ${res.status}`); return res.json() })
      .then((data) => setProvinces(data.features.map((f) => f.properties).sort((a, b) => a.name.localeCompare(b.name))))
      .catch((e) => console.warn('Province list unavailable', e))
  }, [])
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

  const selected = barangays?.list.find((b) => b.psgc === selectedId)

  // A municipality's records and images load when it is first needed: opened, holding the selected barangay, or in focus.
  const [cardId, selectedMuni] = [municipality?.psgc, selected?.munipsgc]
  useEffect(() => {
    if (!floods) return
    const put = (id, v) => setManifests((m) => ({ ...m, [id]: v }))
    for (const id of new Set([cardId, selectedMuni, focusId])) {
      if (!id || requested.current.has(id)) continue
      requested.current.add(id)
      if (!floods.municipalities[id]) {
        put(id, { status: 'failed' })
        continue
      }
      put(id, { status: 'loading' })
      loadMunicipality(floods, id).then(
        (data) => put(id, { status: 'ok', data }),
        (e) => {
          console.warn(e)
          put(id, { status: 'failed' })
        },
      )
    }
  }, [floods, cardId, selectedMuni, focusId])

  const select = useCallback(
    (id, locate) => {
      setSelectedId(id)
      setProvince(null)
      setMunicipality(null)
      const b = barangays?.list.find((x) => x.psgc === id)
      if (b) setFocusId(b.munipsgc)
      if (locate && b) setFit({ bounds: b.bounds })
    },
    [barangays],
  )

  const openMunicipality = useCallback((m) => {
    setProvince(null)
    setSelectedId(null)
    setMunicipality(m)
    setFocusId(m.psgc)
    setFit({ bounds: m.bounds })
  }, [])

  const focus = useMemo(() => {
    const entry = floods?.municipalities[focusId]
    return entry ? { psgc: focusId, corners: entry.corners } : null
  }, [floods, focusId])

  return (
    <div className="relative h-full overflow-hidden">
      <div className="absolute inset-0">
        <MapStage barangays={barangays} floods={floods} manifest={manifests[focusId]?.data ?? null} focus={focus} frame={frame} selectedId={selectedId} show={show} fit={fit} homeTick={homeTick} time={time} onSelect={select} onMunicipality={openMunicipality} onProvince={(p) => { setProvince(p); setSelectedId(null); setMunicipality(null) }} onCenter={setFocusId} onStatus={report} onMap={setMap} />
        <Navbar list={barangays?.list ?? []} municipalities={barangays?.municipalities ?? []} frames={floods?.frames.length} boundariesReady={!!barangays} onSelect={select} onMunicipality={openMunicipality} />
        <Status status={status} />
        <label className="pointer-events-auto absolute left-3 top-20 z-10 rounded-xl bg-chalk p-2 shadow-float">
          <span className="sr-only">Select a province</span>
          <select aria-label="Select a province" value={province?.code ?? ''} onChange={(e) => { setProvince(provinces.find((p) => p.code === e.target.value) ?? null); setSelectedId(null); setMunicipality(null) }} className="max-w-52 rounded-lg bg-chalk px-2 py-1 text-sm text-ink">
            <option value="">Select a province</option>
            {provinces.map((p) => <option key={p.code} value={p.code}>{p.name} · {p.region}</option>)}
          </select>
        </label>
        {province && <aside aria-label={`${province.name} province`} className="pointer-events-auto absolute right-3 top-20 z-10 w-72 rounded-2xl bg-chalk p-4 shadow-float">
          <button type="button" onClick={() => setProvince(null)} aria-label="Close province details" className="float-right rounded-lg px-2 py-1 text-sm text-muted hover:bg-cobalt-tint">Close</button>
          <h2 className="text-xl font-medium">{province.name}</h2>
          <p className="mt-1 text-sm text-muted">{province.region} · {province.code}</p>
          <p className="mt-3 text-sm">Province-wide flood observations are not loaded. Unavailable does not mean dry.</p>
        </aside>}
        {selected && <BarangayCard barangay={selected} states={floods?.states} manifest={manifests[selected.munipsgc]} frames={floods?.frames ?? []} frame={frame} onClose={() => setSelectedId(null)} onLocate={(b) => setFit({ bounds: b.bounds })} onFrame={setFrame} />}
        {municipality && <MunicipalityCard municipality={municipality} psgcs={barangays.list.filter((b) => b.munipsgc === municipality.psgc).map((b) => b.psgc)} floods={floods} onFrame={setFrame} onClose={() => setMunicipality(null)} />}
        {floods && <Legend frame={floods.frames[frame]} />}
        <MapControls map={map} show={show} onShow={setShow} onHome={() => setHomeTick((t) => t + 1)} minutes={minutes} onMinutes={setClockOverride} followingPass={clockOverride == null && !!pass} onFollowPass={pass ? () => setClockOverride(null) : null} />
        <LakeChart lake={floods?.lake} frames={floods?.frames ?? []} frame={frame} />
        <Timeline floods={floods} frame={frame} onFrame={setFrame} />
        <Credits />
      </div>
    </div>
  )
}
