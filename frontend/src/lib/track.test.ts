import { describe, it } from 'vitest'

describe('track (Wave 0 stubs — implementations land in Plan 05)', () => {
  it.todo('normalizeTrackPoints maps GPS coords so all values are in [0,1]')
  it.todo('normalizeTrackPoints handles empty input, returns []')
  it.todo('trackToSvgPath returns string starting with M for non-empty input')
  it.todo('smoothMovingAverage window=7 reduces noise without shifting point count')
})
