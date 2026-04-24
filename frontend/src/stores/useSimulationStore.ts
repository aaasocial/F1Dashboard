import { create } from 'zustand'
import type { SimulationResult, SSEModuleEvent } from '../lib/types'

export interface RunParams { raceId: string; driverCode: string; stintIndex: number }

interface SimulationState {
  data: SimulationResult | null
  loading: boolean
  error: string | null
  moduleProgress: SSEModuleEvent | null
  selectedRaceId: string | null
  selectedDriverCode: string | null
  selectedStintIndex: number | null
  sessionId: string | null
  lastRunParams: RunParams | null
  setSimulationData: (data: SimulationResult) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setModuleProgress: (progress: SSEModuleEvent | null) => void
  setSelection: (raceId: string, driverCode: string, stintIndex: number) => void
  setSessionId: (id: string | null) => void
  setLastRunParams: (p: RunParams | null) => void
  reset: () => void
}

export const useSimulationStore = create<SimulationState>(set => ({
  data: null,
  loading: false,
  error: null,
  moduleProgress: null,
  selectedRaceId: null,
  selectedDriverCode: null,
  selectedStintIndex: null,
  sessionId: null,
  lastRunParams: null,
  setSimulationData: data => {
    set({ data, loading: false, error: null })
    // xZoom resets to full range on new simulation load (CONTEXT.md discretion)
    import('./useUIStore').then(m => m.useUIStore.getState().setXZoom(null))
  },
  setLoading: loading => set({ loading }),
  setError: error => set({ error, loading: false }),
  setModuleProgress: moduleProgress => set({ moduleProgress }),
  setSelection: (raceId, driverCode, stintIndex) =>
    set({ selectedRaceId: raceId, selectedDriverCode: driverCode, selectedStintIndex: stintIndex }),
  setSessionId: id => set({ sessionId: id }),
  setLastRunParams: p => set({ lastRunParams: p }),
  reset: () => set({ data: null, loading: false, error: null, moduleProgress: null }),
}))
