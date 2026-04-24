// fmtLapTime: seconds → "M:SS.SSS"
// Source: design reference cockpit-lap.jsx fmtLapTime
export function fmtLapTime(seconds: number): string {
  if (!isFinite(seconds)) return '—:—.—'
  const m = Math.floor(seconds / 60)
  const s = seconds - m * 60
  return `${m}:${s.toFixed(3).padStart(6, '0')}`
}

// fmtDelta: delta seconds → "+0.123" / "–0.123" / "±0.000"
// Uses en-dash (–) for negative, not hyphen (-)
export function fmtDelta(d: number | null): string {
  if (d == null) return '—'
  if (!isFinite(d)) return '—'
  const sign = d > 0 ? '+' : d < 0 ? '–' : '±'
  return `${sign}${Math.abs(d).toFixed(3)}`
}

// fmtCI: CI triplet → "95.2 ±7.2"
export function fmtCI(ci: { mean: number; lo_95: number; hi_95: number }, digits = 1): string {
  const half = (ci.hi_95 - ci.lo_95) / 2
  return `${ci.mean.toFixed(digits)} ±${half.toFixed(digits)}`
}

// fmtTemp: temperature with CI range → "103° ±6°"
export function fmtTemp(ci: { mean: number; lo_95: number; hi_95: number }): string {
  return `${ci.mean.toFixed(0)}° ±${((ci.hi_95 - ci.lo_95) / 2).toFixed(0)}°`
}

// fmtGrip: grip coefficient → "1.42 ±0.03"
export function fmtGrip(ci: { mean: number; lo_95: number; hi_95: number }): string {
  return fmtCI(ci, 3)
}

// fmtEnergy: cumulative energy MJ → "18.4 MJ"
export function fmtEnergy(ci: { mean: number; lo_95: number; hi_95: number }): string {
  return `${ci.mean.toFixed(1)} MJ`
}

// fmtSlip: slip angle degrees → "3.2°"
export function fmtSlip(ci: { mean: number; lo_95: number; hi_95: number }): string {
  return `${ci.mean.toFixed(1)}°`
}
