export interface CI {
  mean: number
  lo_95: number
  hi_95: number
}

export interface LapData {
  lap_number: number
  stint_age: number
  lap_time: CI
  sliding_power_total: CI
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

export type Corner = 'fl' | 'fr' | 'rl' | 'rr'

export interface SimulationMeta {
  race: { id: string; name: string; round: number; season: number; circuit: string }
  driver: { code: string; number: number; name: string; team: string; teamColor: string }
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
  track: [number, number][]
  sectorBounds: [number, number][]
  turns: Array<{ n: number; at: number }>
}

export interface SSEModuleEvent {
  module: number
  name: string
  lap_count: number
}
