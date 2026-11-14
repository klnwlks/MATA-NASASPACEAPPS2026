// Low-poly tree parts for three.js, Z-up and in metres: a lumpy two-lobe crown, a trunk, a ground contact
// patch, and a 20-triangle crown for distant trees.
import { CircleGeometry, CylinderGeometry, DirectionalLight, HemisphereLight, IcosahedronGeometry, MeshBasicMaterial, MeshLambertMaterial } from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

export const GREENS = [0x3f7f3a, 0x4f9142, 0x5d9e48, 0x2f6b35, 0x6aa651]

// Stable pseudo-random in [0, 1) per tree, so trees look the same on every load.
export const hash = (lon, lat) => {
  const v = Math.sin(lon * 12.9898e4 + lat * 78.233e4) * 43758.5453
  return v - Math.floor(v)
}

function crown() {
  const a = new IcosahedronGeometry(1, 1).toNonIndexed().scale(2.6, 2.6, 2.2)
  const b = new IcosahedronGeometry(1, 0).toNonIndexed().scale(1.9, 1.9, 1.8).translate(0.6, 0.4, 1.6)
  const g = mergeGeometries([a, b])
  const p = g.attributes.position
  for (let i = 0; i < p.count; i++) {
    const j = (hash(i, i * 0.37) - 0.5) * 0.35 // hand-made silhouette, not a perfect ball
    p.setXYZ(i, p.getX(i) * (1 + j), p.getY(i) * (1 + j), p.getZ(i) * (1 + j * 0.6))
  }
  g.translate(0, 0, 5.2).computeVertexNormals() // returns nothing, so return g separately
  return g
}

export function treeParts() {
  const geo = {
    crown: crown(),
    trunk: new CylinderGeometry(0.25, 0.4, 4, 6, 1, true).rotateX(Math.PI / 2).translate(0, 0, 2),
    shadow: new CircleGeometry(3, 10).translate(0.8, -0.8, 0.15), // offset away from the sun
    far: new IcosahedronGeometry(1, 0).scale(2.6, 2.6, 2.4).translate(0, 0, 5.2),
  }
  const leaves = new MeshLambertMaterial({ flatShading: true })
  const mat = {
    crown: leaves,
    far: leaves,
    trunk: new MeshLambertMaterial({ color: 0x6e4f33 }),
    shadow: new MeshBasicMaterial({ color: 0x2a2416, transparent: true, opacity: 0.22, depthWrite: false }),
  }
  // Warm late-afternoon sun from the west, matching the map's extrusion light.
  const sun = new DirectionalLight(0xfff1d6, 2.2)
  sun.position.set(-0.6, -0.4, 1)
  const lights = [sun, new HemisphereLight(0xdff0ff, 0x6b5a3a, 1.3)]
  const dispose = () => [...Object.values(geo), ...Object.values(mat)].forEach((x) => x.dispose())
  return { geo, mat, lights, dispose }
}
