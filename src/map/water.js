// Flood frames as a lit water surface: one terrain-following mesh covering the frame, drawn by three.js after the
// extrusions and trees, so roofs and crowns above the surface stay dry and the parts below it read as submerged.
// Cost: one 32k-vertex mesh, a texture swap per frame, a cheap fragment shader; ripples repaint at RIPPLE_FPS.
// The surface height is a visual cue (lake stage above its two-year low, see floodRise), not measured depth.
import { BufferAttribute, Camera, Color, DoubleSide, Matrix4, Mesh, NearestFilter, PlaneGeometry, Scene, ShaderMaterial, TextureLoader, Vector2, Vector3, Vector4, WebGLRenderer } from 'three'
import { MercatorCoordinate } from 'maplibre-gl'

const RIPPLE_FPS = 12
const DEM_N = 2 ** 12 // the terrain's own tile level, so the surface follows the ground MapLibre draws
const [NX, NY] = [160, 200]

// Shared with sun.js so the water takes the same sky, horizon and sun as the rest of the map.
const light = { uSky: { value: new Color() }, uHorizon: { value: new Color() }, uSunDir: { value: new Vector3(0, 0, 1) }, uSun: { value: 1 }, uAmb: { value: 1 } }
export function setWaterLight(p, sun) {
  const [az, alt] = [(sun.azimuth * Math.PI) / 180, (sun.altitude * Math.PI) / 180]
  light.uSky.value.set(p.sky)
  light.uHorizon.value.set(p.horizon)
  light.uSunDir.value.set(Math.sin(az) * Math.cos(alt), Math.cos(az) * Math.cos(alt), Math.sin(alt))
  light.uSun.value = p.sun
  light.uAmb.value = p.ambient / 1.3
}

// Metres of surface above the ground: 0.3 m plus the lake stage at the frame time over the series low.
export function floodRise(lake, utc) {
  const pts = lake?.points
  if (!pts?.length) return 0.5
  const t = Date.parse(utc)
  const next = pts.findIndex((p) => Date.parse(p.utc) >= t)
  const [a, b] = [pts[Math.max(next - 1, 0)], next === -1 ? pts.at(-1) : pts[next]]
  const span = Date.parse(b.utc) - Date.parse(a.utc)
  const stage = span > 0 ? a.m + ((b.m - a.m) * (t - Date.parse(a.utc))) / span : b.m
  return 0.3 + stage - Math.min(...pts.map((p) => p.m))
}

// Terrarium tiles around the frame stitched into one metres grid.
async function loadDem(root, nw, se) {
  const [x0, x1, y0, y1] = [Math.floor(nw.x * DEM_N), Math.floor(se.x * DEM_N), Math.floor(nw.y * DEM_N), Math.floor(se.y * DEM_N)]
  const [w, h] = [(x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256]
  const ctx = new OffscreenCanvas(w, h).getContext('2d', { willReadFrequently: true })
  const jobs = []
  for (let x = x0; x <= x1; x++)
    for (let y = y0; y <= y1; y++)
      jobs.push(fetch(`${root}data/terrain/12/${x}/${y}.png`).then((r) => r.blob()).then(createImageBitmap).then((img) => ctx.drawImage(img, (x - x0) * 256, (y - y0) * 256)))
  await Promise.all(jobs)
  const px = ctx.getImageData(0, 0, w, h).data
  return { x0, y0, w, h, m: Float32Array.from({ length: w * h }, (_, i) => px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768) }
}

function surface(dem, nw, se, origin, s) {
  const g = new PlaneGeometry(1, 1, NX, NY)
  const pos = g.attributes.position
  const elev = new Float32Array(pos.count)
  for (let k = 0; k < pos.count; k++) {
    const [mx, my] = [nw.x + ((se.x - nw.x) * (k % (NX + 1))) / NX, nw.y + ((se.y - nw.y) * Math.floor(k / (NX + 1))) / NY]
    pos.setXYZ(k, (mx - origin.x) / s, -(my - origin.y) / s, 0)
    const [fx, fy] = [Math.min(dem.w - 1.001, Math.max(0, (mx * DEM_N - dem.x0) * 256 - 0.5)), Math.min(dem.h - 1.001, Math.max(0, (my * DEM_N - dem.y0) * 256 - 0.5))]
    const [ix, iy, ax, ay] = [Math.floor(fx), Math.floor(fy), fx % 1, fy % 1]
    const at = (a, b) => dem.m[(iy + b) * dem.w + ix + a]
    elev[k] = (at(0, 0) * (1 - ax) + at(1, 0) * ax) * (1 - ay) + (at(0, 1) * (1 - ax) + at(1, 1) * ax) * ay
  }
  return g.setAttribute('elev', new BufferAttribute(elev, 1))
}

const VERT = /* glsl */ `
attribute float elev;
uniform float uEx, uRise;
varying vec3 vW;
varying vec2 vUv;
void main() {
  vUv = vec2(uv.x, 1.0 - uv.y);
  vW = vec3(position.xy, elev * uEx + uRise);
  gl_Position = projectionMatrix * vec4(vW, 1.0);
}`

// Shared by the water and the overlays.
const MASK = /* glsl */ `
uniform sampler2D uMask;
uniform vec2 uSize;
varying vec2 vUv;
// The mask stores the class in alpha, so filtering it would blend classes. Instead take the four nearest texels,
// bilinearly weight each class's indicator, and threshold that field: smooth contours, no class mixing.
// Returns (any class, water, confident water).
vec3 field(vec2 uv) {
  vec2 f = uv * uSize - 0.5, w = fract(f), c = floor(f);
  vec3 s = vec3(0.0);
  for (int k = 0; k < 4; k++) {
    vec2 o = vec2(k & 1, k >> 1);
    float t = texture2D(uMask, (c + o + 0.5) / uSize).a, wt = (o.x > 0.5 ? w.x : 1.0 - w.x) * (o.y > 0.5 ? w.y : 1.0 - w.y);
    s += wt * vec3(step(0.05, t), step(0.4, t), step(0.76, t));
  }
  return s;
}`
// Mask alpha is the frame's class: 215 flood, 170 low confidence, 70 unknown veil (scripts/flood_summary.py).
const FRAG = MASK + /* glsl */ `
uniform vec3 uEye, uSky, uHorizon, uSunDir;
uniform float uTime, uSun, uAmb;
varying vec3 vW;
void main() {
  vec3 F = field(vUv);
  float wet = F.y, sure = F.z;
  float edge = smoothstep(0.35, 0.65, wet);
  if (edge < 0.01) {
    // Dry pixels scattered inside the veil are noise at this scale: average a ring 3 texels out to close holes up to ~4 px.
    vec2 d = 3.0 / uSize;
    float seen = (F.x + field(vUv + vec2(d.x, 0.0)).x + field(vUv - vec2(d.x, 0.0)).x + field(vUv + vec2(0.0, d.y)).x + field(vUv - vec2(0.0, d.y)).x) / 5.0;
    float veil = smoothstep(0.4, 0.7, seen);
    if (veil < 0.01) discard;
    gl_FragColor = vec4(vec3(0.19), 0.27 * veil);
    return;
  }
  float conf = smoothstep(0.3, 0.7, sure / wet); // low-confidence water is one solid patch, paler and fainter
  vec3 to = uEye - vW;
  float dist = length(to);
  vec3 v = to / dist;
  // Three crossing sine waves; the slope is their analytic gradient, calmed with distance so far ripples don't shimmer.
  vec2 p = vW.xy, k1 = vec2(0.31, 0.12), k2 = vec2(-0.17, 0.44), k3 = vec2(0.82, -0.51);
  vec2 grad = cos(dot(k1, p) + uTime * 0.8) * k1 * 0.05 + cos(dot(k2, p) - uTime * 1.1) * k2 * 0.035 + cos(dot(k3, p) + uTime * 1.7) * k3 * 0.018;
  vec3 n = normalize(vec3(-grad / (1.0 + dist / 600.0), 1.0));
  vec3 r = reflect(-v, n);
  float fres = 0.2 + 0.8 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
  vec3 mirror = mix(uHorizon, uSky, clamp(r.z * 1.5, 0.0, 1.0));
  vec3 col = mix(vec3(0.03, 0.28, 0.6) * uAmb, mirror, fres) + vec3(1.0, 0.93, 0.8) * pow(max(dot(r, uSunDir), 0.0), 220.0) * uSun;
  col = mix(col, vec3(0.2, 0.6, 0.7) * uAmb, max(1.0 - smoothstep(0.65, 1.0, wet), (1.0 - conf) * 0.6) * 0.5); // paler where shallow or unsure
  col = mix(col, uHorizon, smoothstep(4000.0, 12000.0, dist)); // hazes out with the sky
  gl_FragColor = vec4(col, mix(0.88, 0.97, fres) * edge * mix(0.6, 1.0, conf));
  #include <colorspace_fragment>
}`

// Overlays are one class (alpha > 0), so the "any" channel of field() is their coverage.
const FLAT = MASK + /* glsl */ `
uniform vec3 uColor;
void main() {
  float a = smoothstep(0.35, 0.65, field(vUv).x);
  if (a < 0.01) discard;
  gl_FragColor = vec4(uColor, 0.78 * a);
  #include <colorspace_fragment>
}`

// Resolves once the layer exists: { set(url, rise) } swaps the frame and the surface height.
export async function addWaterLayer(map, corners, root) {
  const [nw, se] = [MercatorCoordinate.fromLngLat(corners[0], 0), MercatorCoordinate.fromLngLat(corners[2], 0)]
  const dem = await loadDem(root, nw, se)
  if (!map.getStyle()) return null // map removed while loading

  const origin = MercatorCoordinate.fromLngLat(map.getCenter(), 0)
  const s = origin.meterInMercatorCoordinateUnits()
  const toLocal = new Matrix4().makeTranslation(origin.x, origin.y, 0).scale(new Vector3(s, -s, s))
  const mat = new ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, side: DoubleSide, uniforms: { ...light, uMask: { value: null }, uSize: { value: new Vector2(1, 1) }, uEye: { value: new Vector3() }, uTime: { value: 0 }, uEx: { value: 1 }, uRise: { value: 0.5 } } })
  const mesh = new Mesh(surface(dem, nw, se, origin, s), mat)
  mesh.frustumCulled = false
  const scene = new Scene().add(mesh)
  const [camera, inv, eye, loader] = [new Camera(), new Matrix4(), new Vector4(), new TextureLoader()]
  const u = mat.uniforms
  let [renderer, visible] = [null, false]
  const seqs = new Map()
  const swap = (uniforms, url, then) => {
    if (uniforms.uMask.value?.userData.src === url) return then()
    const mine = (seqs.get(uniforms) ?? 0) + 1
    seqs.set(uniforms, mine)
    loader.load(url, (t) => {
      if (mine !== seqs.get(uniforms) || !map.getStyle()) return t.dispose()
      Object.assign(t, { flipY: false, generateMipmaps: false, minFilter: NearestFilter, magFilter: NearestFilter, userData: { src: url } })
      uniforms.uSize.value.set(t.image.width, t.image.height)
      uniforms.uMask.value?.dispose()
      uniforms.uMask.value = t
      then()
      map.triggerRepaint()
    })
  }
  const overlays = Object.fromEntries(
    [['coherence', '#B7791F'], ['nisar', '#0E9DB8']].map(([key, hex]) => {
      const m = new ShaderMaterial({ vertexShader: VERT, fragmentShader: FLAT, transparent: true, depthWrite: false, side: DoubleSide, uniforms: { uMask: { value: null }, uSize: { value: new Vector2(1, 1) }, uColor: { value: new Color(hex) }, uEx: u.uEx, uRise: u.uRise } })
      const o = new Mesh(mesh.geometry, m)
      Object.assign(o, { frustumCulled: false, visible: false, renderOrder: 1 })
      scene.add(o)
      return [key, { mat: m, mesh: o, url: null }]
    }),
  )
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
  const timer = setInterval(() => visible && !document.hidden && !reduced.matches && map.triggerRepaint(), 1000 / RIPPLE_FPS)

  map.addLayer({
    id: 'flood',
    type: 'custom',
    renderingMode: '3d',
    onAdd: (_, gl) => {
      renderer = new WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: true })
      renderer.autoClear = false
    },
    render: (_, args) => {
      if (!u.uMask.value) return
      camera.projectionMatrix.fromArray(args.defaultProjectionData.mainMatrix).multiply(toLocal)
      eye.set(0, 0, 1, 0).applyMatrix4(inv.copy(camera.projectionMatrix).invert()) // the eye is where w = 0
      u.uEye.value.set(eye.x / eye.w, eye.y / eye.w, eye.z / eye.w)
      u.uTime.value = (performance.now() / 1000) % 600
      u.uEx.value = map.getTerrain()?.exaggeration ?? 0
      renderer.resetState()
      renderer.render(scene, camera)
    },
    onRemove: () => {
      clearInterval(timer)
      mesh.geometry.dispose()
      for (const m of [mat, ...Object.values(overlays).map((o) => o.mat)]) {
        m.uniforms.uMask.value?.dispose()
        m.dispose()
      }
    },
  })

  return {
    set: (url, rise) => swap(u, url, () => ((u.uRise.value = rise), (visible = true))),
    // Evidence overlay (coherence, nisar): same smoothed mask, flat colour, hidden when its source has no pass here.
    overlay(key, url, on) {
      const o = overlays[key]
      o.mesh.visible = !!url && on
      if (o.mesh.visible && o.url !== url) swap(o.mat.uniforms, (o.url = url), () => {})
      map.triggerRepaint()
    },
  }
}
