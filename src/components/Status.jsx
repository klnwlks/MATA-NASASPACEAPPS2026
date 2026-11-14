const MESSAGES = {
  terrain: { loading: ['Terrain · loading', 'GLO-30 tiles'], failed: ['Terrain · unavailable', 'Flat fallback. Elevation not rendered.'] },
  basemap: { loading: ['Buildings and roads · loading', 'OSM extract'], failed: ['Buildings and roads · failed', 'Basemap not drawn.'] },
  imagery: { failed: ['Imagery · unavailable', 'EOX tiles unreachable. Vector colours only.'] },
  boundaries: { loading: ['Boundaries · loading', 'COD-AB polygons'], failed: ['Boundaries · failed', 'Selection disabled.'] },
  webgl: { failed: ['WebGL · unavailable', "This browser can't draw the 3D map."] },
}
const tone = { loading: 'text-muted', failed: 'text-fail' }

export default function Status({ status }) {
  const items = Object.entries(status)
    .map(([key, s]) => [key, s, MESSAGES[key][s]])
    .filter(([, , m]) => m)
  if (!items.length) return null
  return (
    <ul role="status" className="pointer-events-none absolute inset-x-3 top-[5rem] z-10 flex flex-col items-center gap-2">
      {items.map(([key, s, [title, note]]) => (
        <li key={key} className="pointer-events-auto rounded-xl bg-chalk px-4 py-2 shadow-float">
          <p className={`text-sm font-medium ${tone[s]}`}>{title}</p>
          <p className="text-xs text-muted">{note}</p>
        </li>
      ))}
    </ul>
  )
}
