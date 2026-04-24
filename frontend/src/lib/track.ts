// Track geometry utilities for MapPanel
// Source: design reference Pattern 9 + data.jsx buildBahrainPath

/**
 * Normalize track points from any coordinate range to [0,1] in both axes.
 * Preserves aspect ratio by using the larger of xRange/yRange as the scale divisor.
 */
export function normalizeTrackPoints(pts: [number, number][]): [number, number][] {
  if (pts.length === 0) return []
  if (pts.length === 1) return [[0, 0]]

  const xs = pts.map(p => p[0])
  const ys = pts.map(p => p[1])
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const yMin = Math.min(...ys)
  const yMax = Math.max(...ys)
  const scale = Math.max(xMax - xMin, yMax - yMin)

  if (scale === 0) return pts.map(() => [0, 0] as [number, number])

  return pts.map(([x, y]) => [
    (x - xMin) / scale,
    (y - yMin) / scale,
  ] as [number, number])
}

/**
 * Simple moving average smoothing for GPS noise reduction.
 * Window=7 is sufficient for FastF1 GPS data (Savitzky-Golay done server-side).
 */
export function smoothMovingAverage(pts: [number, number][], window = 7): [number, number][] {
  if (pts.length === 0) return []
  const half = Math.floor(window / 2)
  return pts.map((_, i) => {
    const slice = pts.slice(Math.max(0, i - half), i + half + 1)
    const x = slice.reduce((a, p) => a + p[0], 0) / slice.length
    const y = slice.reduce((a, p) => a + p[1], 0) / slice.length
    return [x, y] as [number, number]
  })
}

/**
 * Convert normalized track points to SVG path string.
 * Closes with Z for a complete circuit loop.
 */
export function trackToSvgPath(pts: [number, number][]): string {
  if (pts.length === 0) return ''
  return (
    pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(4)} ${p[1].toFixed(4)}`).join(' ') +
    ' Z'
  )
}

/**
 * Find the index of the nearest track point to a given coordinate.
 * Used to position the car dot at the start of a given lap.
 */
export function findNearestPoint(pts: [number, number][], x: number, y: number): number {
  if (pts.length === 0) return 0
  let best = 0
  let bestDist = Infinity
  for (let i = 0; i < pts.length; i++) {
    const dx = pts[i][0] - x
    const dy = pts[i][1] - y
    const d = dx * dx + dy * dy
    if (d < bestDist) {
      bestDist = d
      best = i
    }
  }
  return best
}

/**
 * Get the track point index corresponding to a lap fraction (0..1 around the full circuit).
 */
export function lapFracToTrackIndex(trackLen: number, frac: number): number {
  return Math.floor(Math.max(0, Math.min(1, frac)) * (trackLen - 1))
}
