import { describe, it, expect } from 'vitest'
import { normalizeTrackPoints, trackToSvgPath, smoothMovingAverage, findNearestPoint } from './track'

describe('normalizeTrackPoints', () => {
  it('maps all coordinates to [0,1] range', () => {
    const result = normalizeTrackPoints([[0, 0], [10, 5], [20, 0]])
    for (const [x, y] of result) {
      expect(x).toBeGreaterThanOrEqual(0)
      expect(x).toBeLessThanOrEqual(1)
      expect(y).toBeGreaterThanOrEqual(0)
      expect(y).toBeLessThanOrEqual(1)
    }
  })

  it('returns [] for empty input', () => {
    expect(normalizeTrackPoints([])).toEqual([])
  })

  it('returns [[0,0]] for single point', () => {
    expect(normalizeTrackPoints([[5, 5]])).toEqual([[0, 0]])
  })

  it('preserves point count', () => {
    const pts: [number, number][] = [[0, 0], [5, 5], [10, 0], [5, -5]]
    expect(normalizeTrackPoints(pts)).toHaveLength(4)
  })
})

describe('trackToSvgPath', () => {
  it('starts with M for non-empty input', () => {
    const result = trackToSvgPath([[0.1, 0.1], [0.5, 0.5], [0.9, 0.1]])
    expect(result).toMatch(/^M/)
  })

  it('contains L for multi-point path', () => {
    const result = trackToSvgPath([[0.1, 0.1], [0.5, 0.5], [0.9, 0.1]])
    expect(result).toContain('L')
  })

  it('ends with Z (closed loop)', () => {
    const result = trackToSvgPath([[0.1, 0.1], [0.5, 0.5], [0.9, 0.1]])
    expect(result).toMatch(/Z$/)
  })

  it('returns empty string for empty input', () => {
    expect(trackToSvgPath([])).toBe('')
  })
})

describe('smoothMovingAverage', () => {
  it('preserves array length', () => {
    const pts: [number, number][] = [[0, 0], [1, 1], [2, 0], [3, 1], [4, 0]]
    expect(smoothMovingAverage(pts, 3)).toHaveLength(5)
  })

  it('returns [] for empty input', () => {
    expect(smoothMovingAverage([])).toEqual([])
  })
})

describe('findNearestPoint', () => {
  it('finds the nearest point index', () => {
    const pts: [number, number][] = [[0, 0], [0.5, 0.5], [1, 0]]
    expect(findNearestPoint(pts, 0.4, 0.4)).toBe(1)
  })

  it('returns 0 for empty pts', () => {
    expect(findNearestPoint([], 0.5, 0.5)).toBe(0)
  })
})
