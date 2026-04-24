import { describe, it, expect } from 'vitest'
import { area, line } from 'd3-shape'
import { scaleLinear } from 'd3-scale'

// Test the D3 path generation logic directly (not the React component)
// This validates the math used in PhysicsChart

type LapDatum = { lap: number; mean: number; lo: number; hi: number }

function makePaths(data: LapDatum[], maxLap: number) {
  const padL = 40, padR = 12, padT = 8, padB = 6
  const w = 480, h = 70
  const iw = w - padL - padR
  const ih = h - padT - padB
  const yMin = 88, yMax = 118

  const sx = scaleLinear().domain([1, maxLap]).range([padL, padL + iw])
  const sy = scaleLinear().domain([yMin, yMax]).range([padT + ih, padT])

  const ciArea = area<LapDatum>().x(d => sx(d.lap)).y0(d => sy(d.lo)).y1(d => sy(d.hi))
  const meanLine = line<LapDatum>().x(d => sx(d.lap)).y(d => sy(d.mean))

  return { ciPath: ciArea(data) ?? '', meanPath: meanLine(data) ?? '' }
}

describe('PhysicsChart D3 path generation', () => {
  const validData: LapDatum[] = [
    { lap: 1, mean: 90, lo: 87, hi: 93 },
    { lap: 2, mean: 93, lo: 90, hi: 96 },
    { lap: 3, mean: 96, lo: 93, hi: 99 },
  ]

  it('CI band path is non-empty for valid 3-lap data', () => {
    const { ciPath } = makePaths(validData, 22)
    expect(ciPath).not.toBe('')
    expect(ciPath.length).toBeGreaterThan(10)
  })

  it('CI band path starts with M (SVG moveto)', () => {
    const { ciPath } = makePaths(validData, 22)
    expect(ciPath).toMatch(/^M/)
  })

  it('mean line path is non-empty for valid data', () => {
    const { meanPath } = makePaths(validData, 22)
    expect(meanPath).not.toBe('')
  })

  it('CI band path is empty string for 0 laps', () => {
    const { ciPath } = makePaths([], 22)
    expect(ciPath).toBe('')
  })

  it('CI band hi values produce lower SVG y than lo values (larger domain = lower y in SVG)', () => {
    // In SVG, y increases downward. sy maps yMax → padT (top), yMin → padT+ih (bottom).
    // hi (higher value) → lower SVG y (visually higher)
    // lo (lower value) → higher SVG y (visually lower)
    // This verifies CI band orientation is correct
    const padL = 40, padT = 8, padB = 6
    const w = 480, h = 70
    const iw = w - padL - 12
    const ih = h - padT - padB
    const sy = scaleLinear().domain([88, 118]).range([padT + ih, padT])
    expect(sy(93)).toBeGreaterThan(sy(99))  // lo (93) has higher SVG y than hi (99)
  })
})
