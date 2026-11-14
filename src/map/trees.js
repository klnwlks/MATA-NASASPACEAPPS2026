// Low-poly 3D trees drawn by three.js inside MapLibre. fill-extrusion can only push polygons straight up,
// which turns trees into prisms. Mapped OSM trees (k=1) and decorative fill (k=0, scripts/trees.py) share
// one mesh; fill is shifted slightly in hue and disclosed in Sources.
import { Camera, Color, InstancedMesh, Matrix4, Quaternion, Scene, Vector3, Vector4, WebGLRenderer } from 'three'
import { MercatorCoordinate } from 'maplibre-gl'
import { GREENS, hash, treeParts } from './treeMesh.js'

const MIN_ZOOM = 14
const CHUNK_Z = 15 // one instanced mesh set per z15 tile (~1.2 km): the unit of culling and level of detail
const NEAR_M = 2500
const FAR_M = 7000

function chunkKey(lon, lat) {
  const n = 2 ** CHUNK_Z
  const y = Math.floor(((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n)
  return `${Math.floor(((lon + 180) / 360) * n)}/${y}`
}

export async function addTreeLayer(map, url, beforeId) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`trees: HTTP ${res.status}`)
  const { features } = await res.json()
  if (!map.getStyle()) return // map removed while loading

  const chunks = new Map()
  for (const f of features)
    for (const [lon, lat, elev] of f.geometry.coordinates) {
      const key = chunkKey(lon, lat)
      if (!chunks.has(key)) chunks.set(key, [])
      chunks.get(key).push([lon, lat, elev, f.properties.k])
    }

  const origin = MercatorCoordinate.fromLngLat(map.getCenter(), 0)
  const s = origin.meterInMercatorCoordinateUnits()
  const toLocal = new Matrix4().makeTranslation(origin.x, origin.y, 0).scale(new Vector3(s, -s, s))
  const scene = new Scene()
  const { geo, mat, lights, dispose } = treeParts()
  scene.add(...lights)
  const meshes = []
  for (const trees of chunks.values()) {
    const set = Object.fromEntries(Object.keys(geo).map((k) => [k, new InstancedMesh(geo[k], mat[k], trees.length)]))
    const color = new Color()
    trees.forEach(([lon, lat, , k], i) => {
      color.setHex(GREENS[Math.floor(hash(lon, lat) * 997) % GREENS.length])
      if (k === 0) color.offsetHSL(0.015, -0.03, 0.02)
      set.crown.setColorAt(i, color)
    })
    set.far.instanceMatrix = set.crown.instanceMatrix
    set.far.instanceColor = set.crown.instanceColor
    meshes.push({ set, trees })
    scene.add(...Object.values(set))
  }

  // Full trees near the camera, simple crowns further out, nothing past the fog.
  // The eye is the point the projection sends to w = 0, so it falls out of the inverted view-projection.
  const inv = new Matrix4()
  const eye = new Vector4()
  const lod = (viewProj) => {
    eye.set(0, 0, 1, 0).applyMatrix4(inv.copy(viewProj).invert())
    const at = new Vector3(eye.x / eye.w, eye.y / eye.w, eye.z / eye.w)
    for (const { set } of meshes) {
      const d = set.crown.boundingSphere.center.distanceTo(at)
      set.crown.visible = set.trunk.visible = set.shadow.visible = d < NEAR_M
      set.far.visible = d >= NEAR_M && d < FAR_M
    }
  }

  // Elevation follows the live terrain exaggeration; trees drop to the plane if terrain fails.
  const place = () => {
    const ex = map.getTerrain()?.exaggeration ?? 0
    const [m, q, up] = [new Matrix4(), new Quaternion(), new Vector3(0, 0, 1)]
    for (const { set, trees } of meshes) {
      trees.forEach(([lon, lat, elev], i) => {
        const r = hash(lon, lat)
        const mc = MercatorCoordinate.fromLngLat([lon, lat], 0)
        const sc = 0.7 + r * 0.7
        m.compose(new Vector3((mc.x - origin.x) / s, -(mc.y - origin.y) / s, elev * ex), q.setFromAxisAngle(up, r * 6.283), new Vector3(sc, sc, sc * (0.9 + r * 0.3)))
        for (const k of ['crown', 'trunk', 'shadow']) set[k].setMatrixAt(i, m)
      })
      for (const mesh of Object.values(set)) {
        mesh.instanceMatrix.needsUpdate = true
        mesh.computeBoundingSphere()
      }
    }
    map.triggerRepaint()
  }
  place()
  map.on('terrain', place)

  const camera = new Camera()
  let renderer
  map.addLayer(
    {
      id: 'trees',
      type: 'custom',
      renderingMode: '3d',
      onAdd: (_, gl) => {
        renderer = new WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: true })
        renderer.autoClear = false
      },
      render: (_, args) => {
        if (map.getZoom() < MIN_ZOOM) return
        camera.projectionMatrix.fromArray(args.defaultProjectionData.mainMatrix).multiply(toLocal)
        lod(camera.projectionMatrix)
        renderer.resetState()
        renderer.render(scene, camera)
      },
      onRemove: () => {
        map.off('terrain', place)
        dispose()
      },
    },
    beforeId,
  )
}
