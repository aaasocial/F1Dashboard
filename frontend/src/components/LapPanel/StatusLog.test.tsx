import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { StatusLog } from './StatusLog'
import { useUIStore } from '../../stores/useUIStore'
import type { LapData, CI } from '../../lib/types'

const ci = (m: number): CI => ({ mean: m, lo_95: m - 1, hi_95: m + 1 })
function mkLap(n: number): LapData {
  return {
    lap_number: n, stint_age: n - 1,
    lap_time: ci(95), sliding_power_total: ci(100),
    t_tread_fl: ci(95), t_tread_fr: ci(95), t_tread_rl: ci(95), t_tread_rr: ci(95),
    grip_fl: ci(1.4), grip_fr: ci(1.4), grip_rl: ci(1.4), grip_rr: ci(1.4),
    e_tire_fl: ci(2), e_tire_fr: ci(2), e_tire_rl: ci(2), e_tire_rr: ci(2),
    slip_angle_fl: ci(3), slip_angle_fr: ci(3), slip_angle_rl: ci(3), slip_angle_rr: ci(3),
  } as LapData
}

const laps = Array.from({ length: 5 }, (_, i) => mkLap(i + 1))

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
  cleanup()
})

describe('StatusLog', () => {
  it('renders log body with non-zero max-height when statusLogCollapsed=false', () => {
    render(<StatusLog laps={laps} />)
    const body = screen.getByTestId('status-log-body')
    // max-height should be the expanded value (140) or auto
    expect(body.style.maxHeight).not.toBe('0px')
    expect(body.style.maxHeight).not.toBe('0')
  })

  it('renders log body with max-height: 0 when statusLogCollapsed=true', () => {
    useUIStore.setState({ statusLogCollapsed: true })
    render(<StatusLog laps={laps} />)
    const body = screen.getByTestId('status-log-body')
    expect(body.style.maxHeight).toBe('0px')
  })

  it('clicking the header calls toggleStatusLog (store action)', () => {
    render(<StatusLog laps={laps} />)
    const header = screen.getByRole('button', { name: /toggle status log/i })
    fireEvent.click(header)
    expect(useUIStore.getState().statusLogCollapsed).toBe(true)
  })

  it('does NOT contain useState(false) for collapse — uses store', () => {
    // This test verifies that clicking header toggles store, not local state
    render(<StatusLog laps={laps} />)
    const header = screen.getByRole('button', { name: /toggle status log/i })
    fireEvent.click(header)
    expect(useUIStore.getState().statusLogCollapsed).toBe(true)
    // Click again — should toggle back
    fireEvent.click(header)
    expect(useUIStore.getState().statusLogCollapsed).toBe(false)
  })
})
