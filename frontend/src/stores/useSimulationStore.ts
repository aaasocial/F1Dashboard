import { create } from 'zustand'
import type { SimulationResult, SSEModuleEvent } from '../lib/types'

interface SimulationState {
  data: SimulationResult | null
  loading: boolean
  error: string | null
  moduleProgress: SSEModuleEvent | null
  selectedRaceId: string | null
  selectedDriverCode: string | null
  selectedStintIndex: number | null
  setSimulationData: (data: SimulationResult) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setModuleProgress: (progress: SSEModuleEvent | null) => void
  setSelection: (raceId: string, driverCode: string, stintIndex: number) => void
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
  setSimulationData: data => set({ data, loading: false, error: null }),
  setLoading: loading => set({ loading }),
  setError: error => set({ error, loading: false }),
  setModuleProgress: moduleProgress => set({ moduleProgress }),
  setSelection: (raceId, driverCode, stintIndex) =>
    set({ selectedRaceId: raceId, selectedDriverCode: driverCode, selectedStintIndex: stintIndex }),
  reset: () => set({ data: null, loading: false, error: null, moduleProgress: null }),
}))
