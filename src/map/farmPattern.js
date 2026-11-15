// Paddy-grid texture for farmland polygons: bund lines in both directions with alternating lighter and darker plots,
// on a transparent tile, registered as a map image. Drawn rather than shipped as a file so the colours stay next to
// the style that uses them.
export const FARM_PATTERN = 'farm-grid'

export function addFarmPattern(map) {
  if (map.hasImage(FARM_PATTERN)) return
  const size = 32
  const half = size / 2
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')
  g.fillStyle = 'rgba(196, 212, 120, 0.45)'
  g.fillRect(0, 0, half, half)
  g.fillRect(half, half, half, half)
  g.fillStyle = 'rgba(120, 146, 60, 0.18)'
  g.fillRect(half, 0, half, half)
  g.fillRect(0, half, half, half)
  g.fillStyle = 'rgba(112, 134, 52, 0.75)'
  g.fillRect(0, 0, size, 1.5)
  g.fillRect(0, half, size, 1.5)
  g.fillRect(0, 0, 1.5, size)
  g.fillRect(half, 0, 1.5, size)
  map.addImage(FARM_PATTERN, g.getImageData(0, 0, size, size), { pixelRatio: 2 })
}
