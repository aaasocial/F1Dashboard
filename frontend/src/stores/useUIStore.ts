import { create } from 'zustand'
import type { Corner } from '../lib/types'

export type Speed = 0.5 | 1 | 2 | 4

interface UIState {
  // Existing state (Phase 5)
  hoveredLap: number | null
  hoveredCorner: Corner | null
  mode: 'live' | 'replay'
  playing: boolean
  pos: number        // float 1.000..MAX_LAP+0.999 — single source of truth
  speed: Speed
  // Phase 6 additions
  statusLogCollapsed: boolean        // D-07
  xZoom: [number, number] | null     // D-22 — null = full range
  mapFullscreen: boolean             // D-06
  shortcutsOpen: boolean             // D-09
  provenanceOpen: boolean            // D-19
  toastMessage: string | null        // D-08, D-15

  // Existing actions (Phase 5)
  setHoveredLap: (lap: number | null) => void
  setHoveredCorner: (corner: Corner | null) => void
  setMode: (mode: 'live' | 'replay') => void
  togglePlaying: () => void
  setPlaying: (playing: boolean) => void
  seek: (pos: number) => void
  setSpeed: (speed: Speed) => void
  // Phase 6 actions
  setStatusLogCollapsed: (v: boolean) => void
  toggleStatusLog: () => void
  setXZoom: (domain: [number, number] | null) => void
  setMapFullscreen: (v: boolean) => void
  setShortcutsOpen: (v: boolean) => void
  setProvenanceOpen: (v: boolean) => void
  showToast: (message: string) => void
  clearToast: () => void
}

export const useUIStore = create<UIState>(set => ({
  hoveredLap: null,
  hoveredCorner: null,
  mode: 'live',
  playing: true,
  pos: 1.0,
  speed: 1,
  statusLogCollapsed: false,
  xZoom: null,
  mapFullscreen: false,
  shortcutsOpen: false,
  provenanceOpen: false,
  toastMessage: null,

  setHoveredLap: lap => set({ hoveredLap: lap }),
  setHoveredCorner: corner => set({ hoveredCorner: corner }),
  // switching to replay pauses — per design reference cockpit-app.jsx onModeChange
  setMode: mode => set({ mode, ...(mode === 'replay' ? { playing: false } : {}) }),
  togglePlaying: () => set(s => ({ playing: !s.playing })),
  setPlaying: playing => set({ playing }),
  seek: pos => set({ pos: Math.max(1.0, pos) }),
  setSpeed: speed => set({ speed }),
  setStatusLogCollapsed: v => set({ statusLogCollapsed: v }),
  toggleStatusLog: () => set(s => ({ statusLogCollapsed: !s.statusLogCollapsed })),
  setXZoom: domain => set({ xZoom: domain }),
  setMapFullscreen: v => set({ mapFullscreen: v }),
  setShortcutsOpen: v => set({ shortcutsOpen: v }),
  setProvenanceOpen: v => set({ provenanceOpen: v }),
  showToast: message => set({ toastMessage: message }),
  clearToast: () => set({ toastMessage: null }),
}))
