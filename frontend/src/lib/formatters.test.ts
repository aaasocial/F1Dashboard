import { describe, it, expect } from 'vitest'
import { fmtLapTime, fmtDelta, fmtCI } from './formatters'

describe('fmtLapTime', () => {
  it('formats 93.851s as "1:33.851"', () => expect(fmtLapTime(93.851)).toBe('1:33.851'))
  it('formats 60s as "1:00.000"', () => expect(fmtLapTime(60.0)).toBe('1:00.000'))
  it('formats 59.999s as "0:59.999"', () => expect(fmtLapTime(59.999)).toBe('0:59.999'))
  it('formats NaN as "—:—.—"', () => expect(fmtLapTime(NaN)).toBe('—:—.—'))
  it('formats Infinity as "—:—.—"', () => expect(fmtLapTime(Infinity)).toBe('—:—.—'))
})

describe('fmtDelta', () => {
  it('positive delta has + prefix', () => expect(fmtDelta(0.123)).toBe('+0.123'))
  it('negative delta has en-dash prefix (–)', () => expect(fmtDelta(-0.123)).toBe('–0.123'))
  it('zero delta has ± prefix', () => expect(fmtDelta(0)).toBe('±0.000'))
  it('null returns em-dash', () => expect(fmtDelta(null)).toBe('—'))
})

describe('fmtCI', () => {
  it('formats mean with half-range', () => {
    const result = fmtCI({ mean: 95.2, lo_95: 88.1, hi_95: 102.3 })
    expect(result).toContain('95.2')
    expect(result).toContain('±')
  })
})
