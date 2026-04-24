import { describe, it, expect } from 'vitest'
import { interpolateViridis } from 'd3-scale-chromatic'
import { tempToViridis, COMPOUND_COLORS, CORNER_COLORS } from './scales'

describe('tempToViridis', () => {
  it('returns a non-empty string for any temperature', () => {
    expect(tempToViridis(60)).toBeTruthy()
    expect(tempToViridis(90)).toBeTruthy()
    expect(tempToViridis(120)).toBeTruthy()
  })

  it('60°C returns near-purple/blue (low viridis end)', () => {
    const color = tempToViridis(60)
    expect(color).toBe(interpolateViridis(0))
  })

  it('120°C returns near-yellow (high viridis end)', () => {
    const color = tempToViridis(120)
    expect(color).toBe(interpolateViridis(1))
  })

  it('clamps below 60°C to same as 60°C', () => {
    expect(tempToViridis(30)).toBe(tempToViridis(60))
  })

  it('clamps above 120°C to same as 120°C', () => {
    expect(tempToViridis(150)).toBe(tempToViridis(120))
  })

  it('90°C returns a midpoint viridis color (different from endpoints)', () => {
    const mid = tempToViridis(90)
    expect(mid).not.toBe(tempToViridis(60))
    expect(mid).not.toBe(tempToViridis(120))
  })
})

describe('COMPOUND_COLORS (FIA standard)', () => {
  it('SOFT is #FF3333', () => expect(COMPOUND_COLORS.SOFT).toBe('#FF3333'))
  it('MEDIUM is #FFD700', () => expect(COMPOUND_COLORS.MEDIUM).toBe('#FFD700'))
  it('HARD is #FFFFFF', () => expect(COMPOUND_COLORS.HARD).toBe('#FFFFFF'))
  it('INTER is #22C55E', () => expect(COMPOUND_COLORS.INTER).toBe('#22C55E'))
  it('WET is #3B82F6', () => expect(COMPOUND_COLORS.WET).toBe('#3B82F6'))
})

describe('CORNER_COLORS (Okabe-Ito)', () => {
  it('fl is #E69F00 (orange)', () => expect(CORNER_COLORS.fl).toBe('#E69F00'))
  it('fr is #56B4E9 (sky)', () => expect(CORNER_COLORS.fr).toBe('#56B4E9'))
  it('rl is #009E73 (teal-green)', () => expect(CORNER_COLORS.rl).toBe('#009E73'))
  it('rr is #F0E442 (yellow)', () => expect(CORNER_COLORS.rr).toBe('#F0E442'))
})
