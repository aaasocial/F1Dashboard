import { describe, it, expect, beforeEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { Scrubber } from './Scrubber'
import { useSimulationStore } from '../../stores/useSimulationStore'
import { useUIStore } from '../../stores/useUIStore'
import type { LapData } from '../../lib/types'

// Minimal CI value helper
const ci = (m: number) => ({ mean: m, lo_95: m - 1, hi_95: m + 1 })

function lap(num: number, stintAge: number): LapData {
  return {
    lap_number: num, stint_age: stintAge,
    lap_time: ci(95), sliding_power_total: ci(100),
    t_tread_fl: ci(100), t_tread_fr: ci(100), t_tread_rl: ci(100), t_tread_rr: ci(100),
    grip_fl: ci(1.3), grip_fr: ci(1.3), grip_rl: ci(1.3), grip_rr: ci(1.3),
    e_tire_fl: ci(2), e_tire_fr: ci(2), e_tire_rl: ci(2), e_tire_rr: ci(2),
    slip_angle_fl: ci(3), slip_angle_fr: ci(3), slip_angle_rl: ci(3), slip_angle_rr: ci(3),
  }
}

beforeEach(() => {
  useSimulationStore.setState({ data: null, loading: false, error: null, moduleProgress: null })
  useUIStore.setState({ pos: 1.0 })
  cleanup()
})

describe('Scrubber', () => {
  it('renders 3 sector segments with the locked hex colors', () => {
    const { getByTestId } = render(<Scrubber maxLap={22} />)
    const s0 = getByTestId('sector-segment-0')
    const s1 = getByTestId('sector-segment-1')
    const s2 = getByTestId('sector-segment-2')
    // jsdom converts hex to rgb
    expect(s0.style.background).toContain('rgb(58, 152, 180)')
    expect(s1.style.background).toContain('rgb(42, 122, 147)')
    expect(s2.style.background).toContain('rgb(29, 98, 120)')
  })

  it('renders no pit markers when no laps have stint_age=0 after lap 1', () => {
    useSimulationStore.setState({
      data: {
        meta: {} as any,
        laps: [lap(1, 0), lap(2, 1), lap(3, 2)],
        track: [], sectorBounds: [], turns: [],
      }
    })
    const { queryAllByTestId } = render(<Scrubber maxLap={3} />)
    expect(queryAllByTestId('pit-marker')).toHaveLength(0)
  })

  it('renders pit markers at laps with lap_number>1 and stint_age=0', () => {
    useSimulationStore.setState({
      data: {
        meta: {} as any,
        laps: [lap(1, 0), lap(2, 1), lap(3, 2), lap(4, 0), lap(5, 1)],
        track: [], sectorBounds: [], turns: [],
      }
    })
    const { queryAllByTestId } = render(<Scrubber maxLap={5} />)
    const pits = queryAllByTestId('pit-marker')
    expect(pits).toHaveLength(1)
    // lap 4 of 5 → (4-1)/(5-1) = 75%
    expect(pits[0].style.left).toBe('75%')
  })

  it('existing pointer-drag: scrubber element has data-testid and pointer cursor', () => {
    const { getByTestId } = render(<Scrubber maxLap={22} />)
    const scrubber = getByTestId('scrubber')
    expect(scrubber).toBeTruthy()
    // React uses event delegation — onPointerDown is wired via React, not as a DOM property
    // Verify the element has the cursor style set (confirms it's the interactive drag container)
    expect(scrubber.style.cursor).toBe('pointer')
  })
})
