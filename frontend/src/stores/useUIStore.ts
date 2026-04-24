import { create } from 'zustand'
import type { Corner } from '../lib/types'

interface UIState {
  hoveredLap: number | null
  hoveredCorner: Corner | null
  mode: 'live' | 'replay'
  playing: boolean
  pos: number        // float 1.000..MAX_LAP+0.999 — single source of truth
  speed: 1 | 2 | 4 | 8
  setHoveredLap: (lap: number | null) => void
  setHoveredCorner: (corner: Corner | null) => void
  setMode: (mode: 'live' | 'replay') => void
  togglePlaying: () => void
  setPlaying: (playing: boolean) => void
  seek: (pos: number) => void
  setSpeed: (speed: 1 | 2 | 4 | 8) => void
}

export const useUIStore = create<UIState>(set => ({
  hoveredLap: null,
  hoveredCorner: null,
  mode: 'live',
  playing: true,
  pos: 1.0,
  speed: 1,
  setHoveredLap: lap => set({ hoveredLap: lap }),
  setHoveredCorner: corner => set({ hoveredCorner: corner }),
  // switching to replay pauses — per design reference cockpit-app.jsx onModeChange
  setMode: mode => set({ mode, ...(mode === 'replay' ? { playing: false } : {}) }),
  togglePlaying: () => set(s => ({ playing: !s.playing })),
  setPlaying: playing => set({ playing }),
  seek: pos => set({ pos: Math.max(1.0, pos) }),
  setSpeed: speed => set({ speed }),
}))
