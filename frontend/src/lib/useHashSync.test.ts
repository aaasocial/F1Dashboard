import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useHashSync } from './useHashSync'
import { useSimulationStore } from '../stores/useSimulationStore'
import { useUIStore } from '../stores/useUIStore'

beforeEach(() => {
  window.location.hash = ''
  useSimulationStore.setState({
    data: null, loading: false, error: null, moduleProgress: null,
    selectedRaceId: null, selectedDriverCode: null, selectedStintIndex: null,
    sessionId: null, lastRunParams: null,
  })
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
})

describe('useHashSync', () => {
  it('restores race/driver/stint/lap from hash on mount', () => {
    window.location.hash = '#race=R1&driver=DR1&stint=2&lap=7'
    renderHook(() => useHashSync())
    expect(useSimulationStore.getState().selectedRaceId).toBe('R1')
    expect(useSimulationStore.getState().selectedDriverCode).toBe('DR1')
    expect(useSimulationStore.getState().selectedStintIndex).toBe(2)
    expect(useUIStore.getState().pos).toBe(7)
  })
  it('does not seek when lap is missing', () => {
    window.location.hash = '#race=R1&driver=DR1&stint=0'
    renderHook(() => useHashSync())
    expect(useUIStore.getState().pos).toBe(1)
  })
  it('writes lap to hash when integer lap floor changes', () => {
    useSimulationStore.setState({ selectedRaceId: 'R1', selectedDriverCode: 'DR1', selectedStintIndex: 0 })
    const { rerender } = renderHook(() => useHashSync())
    act(() => { useUIStore.setState({ pos: 5.6 }) })
    rerender()
    expect(window.location.hash).toContain('lap=5')
    act(() => { useUIStore.setState({ pos: 6.1 }) })
    rerender()
    expect(window.location.hash).toContain('lap=6')
  })
  it('does not write lap when selection is incomplete', () => {
    const { rerender } = renderHook(() => useHashSync())
    act(() => { useUIStore.setState({ pos: 5 }) })
    rerender()
    expect(window.location.hash).toBe('')
  })
})
