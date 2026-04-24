// All predicted metrics use CI triplets — non-negotiable per Phase 4 D-02
export interface CI {
  mean: number
  lo_95: number
  hi_95: number
}

export type Corner = 'fl' | 'fr' | 'rl' | 'rr'

export interface LapData {
  lap_number: number
  stint_age: number
  lap_time: CI
  sliding_power_total: CI
  // Per-corner metrics
  t_tread_fl: CI
  t_tread_fr: CI
  t_tread_rl: CI
  t_tread_rr: CI
  grip_fl: CI
  grip_fr: CI
  grip_rl: CI
  grip_rr: CI
  e_tire_fl: CI
  e_tire_fr: CI
  e_tire_rl: CI
  e_tire_rr: CI
  slip_angle_fl: CI
  slip_angle_fr: CI
  slip_angle_rl: CI
  slip_angle_rr: CI
}

export interface SimulationMeta {
  race: {
    id: string
    name: string
    round: number
    season: number
    circuit: string
  }
  driver: {
    code: string
    number: number
    name: string
    team: string
    teamColor: string
  }
  stint: {
    id: number
    compound: string
    compoundColor: string
    startLap: number
    endLap: number
    lapCount: number
    startAge: number
  }
  calibration_id: number
  model_schema_version: string
  fastf1_version: string
  run_id: string
}

export interface SimulationResult {
  meta: SimulationMeta
  laps: LapData[]
  track: [number, number][]          // normalized [0,1] coords from FastF1 X/Y
  sectorBounds: [number, number][]   // index pairs into track[] for S1/S2/S3
  turns: Array<{ n: number; at: number }> // turn N at fraction 0..1 around lap
}

export interface SSEModuleEvent {
  module: number   // 1–7
  name: string     // e.g. "Kinematics"
  lap_count: number
}

// Raw API response shape from backend (before mapApiResponseToSimulationResult mapper)
// Fields use Python/backend naming; mapper in sse.ts transforms these to SimulationResult
export interface SimulateApiResponse {
  metadata: {
    compound: string
    calibration_id: number
    model_schema_version: string
    fastf1_version: string
    run_id?: string
    [key: string]: unknown
  }
  per_lap: LapData[]
  per_stint: unknown
  per_timestep: unknown
  // Track geometry fields added by Plan 08 backend extension
  track?: [number, number][]
  sector_bounds?: [number, number][]
  turns?: Array<{ n: number; at: number }>
  // Convenience field injected by the SSE endpoint (Plan 08)
  lap_count?: number
}

// Cascade picker data
export interface Race {
  id: string
  name: string
  round: number
  season: number
  circuit: string
}

export interface Driver {
  code: string
  name: string
  team: string
  teamColor: string
}

export interface Stint {
  id: number
  compound: string
  startLap: number
  endLap: number
  lapCount: number
  startAge: number
}

// Helper: get per-corner metric from LapData by Corner key
export function getLapCornerMetric(lap: LapData, metric: string, corner: Corner): CI {
  const key = `${metric}_${corner}` as keyof LapData
  return lap[key] as CI
}
