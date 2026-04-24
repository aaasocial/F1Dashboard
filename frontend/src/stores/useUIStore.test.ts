import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from './useUIStore'

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
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
