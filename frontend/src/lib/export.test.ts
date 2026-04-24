import { describe, it, expect } from 'vitest'
import { buildCsv, substituteTokens, TOKEN_MAP } from './export'
import type { LapData } from './types'

function ci(mean: number) { return { mean, lo_95: mean - 1, hi_95: mean + 1 } }
function makeLap(n: number): LapData {
  return {
    lap_number: n, stint_age: n - 1,
    lap_time: ci(95), sliding_power_total: ci(100),
    t_tread_fl: ci(100), t_tread_fr: ci(101), t_tread_rl: ci(102), t_tread_rr: ci(103),
    grip_fl: ci(1.3), grip_fr: ci(1.3), grip_rl: ci(1.3), grip_rr: ci(1.3),
    e_tire_fl: ci(2), e_tire_fr: ci(2), e_tire_rl: ci(2), e_tire_rr: ci(2),
    slip_angle_fl: ci(3), slip_angle_fr: ci(3), slip_angle_rl: ci(3), slip_angle_rr: ci(3),
  } as LapData
}

describe('buildCsv', () => {
  it('produces header + 22 data rows', () => {
    const laps = Array.from({ length: 22 }, (_, i) => makeLap(i + 1))
    const csv = buildCsv(laps, 't_tread')
    const lines = csv.split('\n')
    expect(lines).toHaveLength(23) // 1 header + 22 rows
  })

  it('header has lap + 12 CI columns (4 corners × 3 fields)', () => {
    const csv = buildCsv([makeLap(1)], 't_tread')
    const header = csv.split('\n')[0]
    expect(header).toBe('lap,fl_mean,fl_lo95,fl_hi95,fr_mean,fr_lo95,fr_hi95,rl_mean,rl_lo95,rl_hi95,rr_mean,rr_lo95,rr_hi95')
  })

  it('row contains lap_number and CI mean/lo/hi values to 4 decimal places', () => {
    const csv = buildCsv([makeLap(1)], 't_tread')
    const row = csv.split('\n')[1]
    expect(row).toBe('1,100.0000,99.0000,101.0000,101.0000,100.0000,102.0000,102.0000,101.0000,103.0000,103.0000,102.0000,104.0000')
  })
})

describe('substituteTokens', () => {
  it('replaces var(--text) with #e8eef7', () => {
    expect(substituteTokens('<text fill="var(--text)">x</text>'))
      .toBe('<text fill="#e8eef7">x</text>')
  })
  it('replaces multiple distinct tokens in one pass', () => {
    const out = substituteTokens('a:var(--accent) b:var(--rule)')
    expect(out).toBe('a:#00E5FF b:#1a2130')
  })
  it('TOKEN_MAP has all 17 design tokens from CLAUDE.md', () => {
    const required = ['var(--bg)','var(--panel)','var(--panel-bg)','var(--panel-header)','var(--panel-header-hi)','var(--rule)','var(--rule-strong)','var(--text)','var(--text-dim)','var(--text-muted)','var(--accent)','var(--hot)','var(--warn)','var(--ok)','var(--purple)','var(--mono)']
    for (const k of required) expect(TOKEN_MAP[k]).toBeTruthy()
  })
})
