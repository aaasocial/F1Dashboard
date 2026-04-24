import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { formatTireMetrics, copyTireMetrics } from './tireClipboard'
import { useUIStore } from '../stores/useUIStore'
import type { LapData, CI } from './types'

const ci = (m: number): CI => ({ mean: m, lo_95: m - 1, hi_95: m + 1 })
const lap: LapData = {
  lap_number: 7, stint_age: 6,
  lap_time: ci(95.234), sliding_power_total: ci(100),
  t_tread_fl: ci(94.16), t_tread_fr: ci(96.0), t_tread_rl: ci(98.5), t_tread_rr: ci(99.1),
  grip_fl: ci(1.314), grip_fr: ci(1.30), grip_rl: ci(1.28), grip_rr: ci(1.27),
  e_tire_fl: ci(3.21), e_tire_fr: ci(3.5), e_tire_rl: ci(3.7), e_tire_rr: ci(3.9),
  slip_angle_fl: ci(2.13), slip_angle_fr: ci(2.0), slip_angle_rl: ci(1.8), slip_angle_rr: ci(1.7),
} as LapData

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('formatTireMetrics', () => {
  it('matches the D-15 example format', () => {
    expect(formatTireMetrics('fl', lap)).toBe('FL | 94.2°C | Grip 1.31μ | Wear 3.2 MJ | Slip 2.1°')
  })
  it('uppercases the corner code', () => {
    expect(formatTireMetrics('rr', lap).startsWith('RR | ')).toBe(true)
  })
  it('formats rear-right corner correctly', () => {
    const result = formatTireMetrics('rr', lap)
    expect(result).toBe('RR | 99.1°C | Grip 1.27μ | Wear 3.9 MJ | Slip 1.7°')
  })
})

describe('copyTireMetrics', () => {
  it('writes the formatted string to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await copyTireMetrics('fl', lap)
    expect(writeText).toHaveBeenCalledWith('FL | 94.2°C | Grip 1.31μ | Wear 3.2 MJ | Slip 2.1°')
  })
  it('shows a COPIED <corner> toast', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await copyTireMetrics('rl', lap)
    expect(useUIStore.getState().toastMessage).toBe('COPIED RL')
  })
  it('still shows toast if clipboard.writeText throws', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await copyTireMetrics('fr', lap)
    expect(useUIStore.getState().toastMessage).toBe('COPIED FR')
  })
})
