function walk(g, fn) {
  if (g.type === 'GeometryCollection') return g.geometries.forEach((x) => walk(x, fn))
  const visit = (c) => (typeof c[0] === 'number' ? fn(c) : c.forEach(visit))
  visit(g.coordinates)
}

// [[west, south], [east, north]] for any GeoJSON geometry.
export function bbox(geometry) {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity
  walk(geometry, ([x, y]) => {
    w = Math.min(w, x); e = Math.max(e, x)
    s = Math.min(s, y); n = Math.max(n, y)
  })
  return [[w, s], [e, n]]
}
