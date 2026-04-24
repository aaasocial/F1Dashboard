import { useUIStore } from '../stores/useUIStore'
import { useSimulationStore } from '../stores/useSimulationStore'
import type { Corner } from './types'

/**
 * Returns true if the keyboard event originated from an editable element.
 * Suppresses shortcut handling so users can type into form controls.
 */
export function isInputFocused(target: EventTarget | null): boolean {
  if (!target) return false
  const el = target as HTMLElement
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return true
  if (el.isContentEditable) return true
  return false
}

/**
 * Compute the lap that starts a sector based on a thirds-of-maxLap fallback
 * (sectorBounds in SimulationResult holds track-geometry indices, not lap numbers).
 * Sector 1 starts at lap 1; S2 at floor(maxLap/3)+1; S3 at floor(2*maxLap/3)+1.
 */
export function sectorBoundaryLaps(maxLap: number): [number, number, number] {
  const s1 = 1
  const s2 = Math.max(1, Math.floor(maxLap / 3) + 1)
  const s3 = Math.max(s2 + 1, Math.floor((2 * maxLap) / 3) + 1)
  return [s1, s2, s3]
}

/**
 * Pure key handler.
 * - Reads store state via .getState() to avoid stale closures (RESEARCH.md Pitfall 1).
 * - Suppresses when an input element is focused.
 * - Calls e.preventDefault() for keys that would scroll/affect default browser behavior.
 */
export function handleKey(e: KeyboardEvent): void {
  if (isInputFocused(e.target)) return

  const ui = useUIStore.getState()
  const sim = useSimulationStore.getState()
  const maxLap = sim.data?.laps.length ?? 22
  const pos = ui.pos

  // Space — play/pause
  if (e.code === 'Space') {
    e.preventDefault()
    ui.togglePlaying()
    return
  }

  // Arrow keys (no Shift) — step ±1 lap
  if (e.code === 'ArrowLeft' && !e.shiftKey) {
    e.preventDefault()
    ui.seek(Math.max(1, Math.floor(pos) - 1))
    return
  }
  if (e.code === 'ArrowRight' && !e.shiftKey) {
    e.preventDefault()
    ui.seek(Math.min(maxLap, Math.floor(pos) + 1))
    return
  }

  // Shift+Arrow — sector jump
  if (e.code === 'ArrowLeft' && e.shiftKey) {
    e.preventDefault()
    const [s1, s2, s3] = sectorBoundaryLaps(maxLap)
    const cur = Math.floor(pos)
    // Jump to start of CURRENT sector if past its start, else previous sector
    let target: number
    if (cur > s3) target = s3
    else if (cur > s2) target = s2
    else target = s1
    if (target === cur) {
      // Already at boundary — go to previous boundary
      target = cur === s3 ? s2 : cur === s2 ? s1 : s1
    }
    ui.seek(target)
    return
  }
  if (e.code === 'ArrowRight' && e.shiftKey) {
    e.preventDefault()
    const [, s2, s3] = sectorBoundaryLaps(maxLap)
    const cur = Math.floor(pos)
    let target: number
    if (cur < s2) target = s2
    else if (cur < s3) target = s3
    else target = maxLap
    ui.seek(target)
    return
  }

  // Home / End
  if (e.code === 'Home') {
    e.preventDefault()
    ui.seek(1)
    return
  }
  if (e.code === 'End') {
    e.preventDefault()
    ui.seek(maxLap)
    return
  }

  // 1/2/3/4 — focus corner
  if (e.key === '1' || e.key === '2' || e.key === '3' || e.key === '4') {
    const cornerMap: Record<string, Corner> = { '1': 'fl', '2': 'fr', '3': 'rl', '4': 'rr' }
    ui.setHoveredCorner(cornerMap[e.key])
    return
  }

  // T — fullscreen map
  if (e.key === 't' || e.key === 'T') {
    ui.setMapFullscreen(!useUIStore.getState().mapFullscreen)
    return
  }

  // E — toggle status log
  if (e.key === 'e' || e.key === 'E') {
    ui.toggleStatusLog()
    return
  }

  // S — copy URL
  if (e.key === 's' || e.key === 'S') {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      void navigator.clipboard.writeText(window.location.href)
    }
    ui.showToast('URL COPIED')
    return
  }

  // ? — shortcuts modal
  if (e.key === '?') {
    ui.setShortcutsOpen(true)
    return
  }

  // Escape — dismiss any open overlay/modal
  if (e.code === 'Escape') {
    ui.setMapFullscreen(false)
    ui.setShortcutsOpen(false)
    ui.setProvenanceOpen(false)
    ui.clearToast()
    return
  }
}
