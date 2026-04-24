import { describe, it, expect, beforeEach, vi } from 'vitest'
import { handleKey, isInputFocused, sectorBoundaryLaps } from './keyboard'
import { useUIStore } from '../stores/useUIStore'
import { useSimulationStore } from '../stores/useSimulationStore'
import type { LapData, CI } from './types'

const ci = (m: number): CI => ({ mean: m, lo_95: m - 1, hi_95: m + 1 })
function mkLap(n: number): LapData {
  return {
    lap_number: n, stint_age: n - 1,
    lap_time: ci(95), sliding_power_total: ci(100),
    t_tread_fl: ci(100), t_tread_fr: ci(100), t_tread_rl: ci(100), t_tread_rr: ci(100),
    grip_fl: ci(1.3), grip_fr: ci(1.3), grip_rl: ci(1.3), grip_rr: ci(1.3),
    e_tire_fl: ci(2), e_tire_fr: ci(2), e_tire_rl: ci(2), e_tire_rr: ci(2),
    slip_angle_fl: ci(3), slip_angle_fr: ci(3), slip_angle_rl: ci(3), slip_angle_rr: ci(3),
  } as LapData
}

function evt(init: Partial<KeyboardEvent> & { target?: EventTarget | null }): KeyboardEvent {
  const e = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init })
  if (init.target !== undefined) {
    Object.defineProperty(e, 'target', { value: init.target, configurable: true })
  } else {
    Object.defineProperty(e, 'target', { value: document.body, configurable: true })
  }
  return e
}

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 5.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
  useSimulationStore.setState({
    data: { meta: {} as any, laps: Array.from({ length: 22 }, (_, i) => mkLap(i + 1)), track: [], sectorBounds: [], turns: [] },
    loading: false, error: null, moduleProgress: null,
  })
})

describe('isInputFocused', () => {
  it('returns false for document.body', () => {
    expect(isInputFocused(document.body)).toBe(false)
  })
  it('returns true for INPUT', () => {
    const inp = document.createElement('input')
    expect(isInputFocused(inp)).toBe(true)
  })
  it('returns true for SELECT', () => {
    const sel = document.createElement('select')
    expect(isInputFocused(sel)).toBe(true)
  })
  it('returns true for TEXTAREA', () => {
    const ta = document.createElement('textarea')
    expect(isInputFocused(ta)).toBe(true)
  })
  it('returns true for contenteditable', () => {
    const div = document.createElement('div')
    div.contentEditable = 'true'
    // jsdom: isContentEditable may not auto-update; force
    Object.defineProperty(div, 'isContentEditable', { value: true })
    expect(isInputFocused(div)).toBe(true)
  })
})

describe('sectorBoundaryLaps', () => {
  it('maxLap=22 → [1, 8, 15]', () => {
    expect(sectorBoundaryLaps(22)).toEqual([1, 8, 15])
  })
  it('maxLap=3 → [1, 2, 3]', () => {
    expect(sectorBoundaryLaps(3)).toEqual([1, 2, 3])
  })
})

describe('handleKey — playback', () => {
  it('Space toggles playing and prevents default', () => {
    const e = evt({ code: 'Space' })
    const spy = vi.spyOn(e, 'preventDefault')
    handleKey(e)
    expect(useUIStore.getState().playing).toBe(false)
    expect(spy).toHaveBeenCalled()
  })
  it('ArrowLeft from pos=5 seeks to 4', () => {
    handleKey(evt({ code: 'ArrowLeft', shiftKey: false }))
    expect(useUIStore.getState().pos).toBe(4)
  })
  it('ArrowLeft from pos=1 clamps to 1', () => {
    useUIStore.setState({ pos: 1 })
    handleKey(evt({ code: 'ArrowLeft', shiftKey: false }))
    expect(useUIStore.getState().pos).toBe(1)
  })
  it('ArrowRight from pos=21 maxLap=22 seeks to 22', () => {
    useUIStore.setState({ pos: 21 })
    handleKey(evt({ code: 'ArrowRight', shiftKey: false }))
    expect(useUIStore.getState().pos).toBe(22)
  })
  it('ArrowRight from pos=22 clamps at 22', () => {
    useUIStore.setState({ pos: 22 })
    handleKey(evt({ code: 'ArrowRight', shiftKey: false }))
    expect(useUIStore.getState().pos).toBe(22)
  })
  it('Home seeks to 1', () => {
    handleKey(evt({ code: 'Home' }))
    expect(useUIStore.getState().pos).toBe(1)
  })
  it('End seeks to maxLap', () => {
    handleKey(evt({ code: 'End' }))
    expect(useUIStore.getState().pos).toBe(22)
  })
})

describe('handleKey — sector jump', () => {
  it('Shift+ArrowRight from pos=5 seeks to 8 (start of S2)', () => {
    useUIStore.setState({ pos: 5 })
    handleKey(evt({ code: 'ArrowRight', shiftKey: true }))
    expect(useUIStore.getState().pos).toBe(8)
  })
  it('Shift+ArrowRight from pos=10 seeks to 15 (start of S3)', () => {
    useUIStore.setState({ pos: 10 })
    handleKey(evt({ code: 'ArrowRight', shiftKey: true }))
    expect(useUIStore.getState().pos).toBe(15)
  })
  it('Shift+ArrowRight from pos=20 seeks to maxLap=22', () => {
    useUIStore.setState({ pos: 20 })
    handleKey(evt({ code: 'ArrowRight', shiftKey: true }))
    expect(useUIStore.getState().pos).toBe(22)
  })
  it('Shift+ArrowLeft from pos=15 seeks to 8', () => {
    useUIStore.setState({ pos: 15 })
    handleKey(evt({ code: 'ArrowLeft', shiftKey: true }))
    expect(useUIStore.getState().pos).toBe(8)
  })
})

describe('handleKey — corner focus', () => {
  it("'1' sets hoveredCorner='fl'", () => {
    handleKey(evt({ key: '1' }))
    expect(useUIStore.getState().hoveredCorner).toBe('fl')
  })
  it("'4' sets hoveredCorner='rr'", () => {
    handleKey(evt({ key: '4' }))
    expect(useUIStore.getState().hoveredCorner).toBe('rr')
  })
})

describe('handleKey — overlays', () => {
  it("'t' toggles mapFullscreen", () => {
    handleKey(evt({ key: 't' }))
    expect(useUIStore.getState().mapFullscreen).toBe(true)
    handleKey(evt({ key: 't' }))
    expect(useUIStore.getState().mapFullscreen).toBe(false)
  })
  it("'e' toggles statusLogCollapsed", () => {
    handleKey(evt({ key: 'e' }))
    expect(useUIStore.getState().statusLogCollapsed).toBe(true)
  })
  it("'?' opens shortcuts modal", () => {
    handleKey(evt({ key: '?' }))
    expect(useUIStore.getState().shortcutsOpen).toBe(true)
  })
  it("Escape closes all overlays", () => {
    useUIStore.setState({ mapFullscreen: true, shortcutsOpen: true, provenanceOpen: true, toastMessage: 'x' })
    handleKey(evt({ code: 'Escape' }))
    const s = useUIStore.getState()
    expect(s.mapFullscreen).toBe(false)
    expect(s.shortcutsOpen).toBe(false)
    expect(s.provenanceOpen).toBe(false)
    expect(s.toastMessage).toBeNull()
  })
})

describe('handleKey — clipboard', () => {
  it("'s' writes window.location.href to clipboard and shows toast", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    handleKey(evt({ key: 's' }))
    expect(writeText).toHaveBeenCalledWith(window.location.href)
    expect(useUIStore.getState().toastMessage).toBe('URL COPIED')
  })
})

describe('handleKey — input focus guard', () => {
  it('does nothing when target is INPUT', () => {
    const inp = document.createElement('input')
    handleKey(evt({ code: 'Space', target: inp }))
    expect(useUIStore.getState().playing).toBe(true) // unchanged
  })
  it('does nothing when target is SELECT', () => {
    const sel = document.createElement('select')
    handleKey(evt({ code: 'ArrowLeft', target: sel }))
    expect(useUIStore.getState().pos).toBe(5) // unchanged
  })
})
