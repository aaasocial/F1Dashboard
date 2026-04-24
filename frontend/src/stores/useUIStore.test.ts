import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from './useUIStore'

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
})

describe('useUIStore', () => {
  it('initial hoveredLap is null', () => {
    expect(useUIStore.getState().hoveredLap).toBeNull()
  })

  it('setHoveredLap(5) sets hoveredLap to 5', () => {
    useUIStore.getState().setHoveredLap(5)
    expect(useUIStore.getState().hoveredLap).toBe(5)
  })

  it('setHoveredLap(null) resets hoveredLap to null', () => {
    useUIStore.getState().setHoveredLap(5)
    useUIStore.getState().setHoveredLap(null)
    expect(useUIStore.getState().hoveredLap).toBeNull()
  })

  it('initial hoveredCorner is null', () => {
    expect(useUIStore.getState().hoveredCorner).toBeNull()
  })

  it('setHoveredCorner("fl") sets hoveredCorner', () => {
    useUIStore.getState().setHoveredCorner('fl')
    expect(useUIStore.getState().hoveredCorner).toBe('fl')
  })

  it('setMode("replay") pauses playing', () => {
    useUIStore.getState().setMode('replay')
    expect(useUIStore.getState().mode).toBe('replay')
    expect(useUIStore.getState().playing).toBe(false)
  })

  it('seek(pos) clamps to minimum 1.0', () => {
    useUIStore.getState().seek(0.5)
    expect(useUIStore.getState().pos).toBe(1.0)
  })

  it('seek(10) sets pos to 10', () => {
    useUIStore.getState().seek(10)
    expect(useUIStore.getState().pos).toBe(10)
  })
})

describe('Phase 6 additions', () => {
  it('default speed is 1', () => {
    expect(useUIStore.getState().speed).toBe(1)
  })
  it('setSpeed(0.5) sets speed to 0.5', () => {
    useUIStore.getState().setSpeed(0.5)
    expect(useUIStore.getState().speed).toBe(0.5)
  })
  it('default statusLogCollapsed is false', () => {
    expect(useUIStore.getState().statusLogCollapsed).toBe(false)
  })
  it('toggleStatusLog flips statusLogCollapsed', () => {
    useUIStore.getState().toggleStatusLog()
    expect(useUIStore.getState().statusLogCollapsed).toBe(true)
    useUIStore.getState().toggleStatusLog()
    expect(useUIStore.getState().statusLogCollapsed).toBe(false)
  })
  it('default xZoom is null', () => {
    expect(useUIStore.getState().xZoom).toBeNull()
  })
  it('setXZoom round-trips a tuple and null', () => {
    useUIStore.getState().setXZoom([5, 15])
    expect(useUIStore.getState().xZoom).toEqual([5, 15])
    useUIStore.getState().setXZoom(null)
    expect(useUIStore.getState().xZoom).toBeNull()
  })
  it('mapFullscreen, shortcutsOpen, provenanceOpen default to false', () => {
    const s = useUIStore.getState()
    expect(s.mapFullscreen).toBe(false)
    expect(s.shortcutsOpen).toBe(false)
    expect(s.provenanceOpen).toBe(false)
  })
  it('showToast/clearToast manage toastMessage', () => {
    useUIStore.getState().showToast('hello')
    expect(useUIStore.getState().toastMessage).toBe('hello')
    useUIStore.getState().clearToast()
    expect(useUIStore.getState().toastMessage).toBeNull()
  })
})
