import type { SimulationResult, LapData, CI } from '../../lib/types'

function hash(n: number): number {
  const s = Math.sin(n * 9301 + 49297) * 233280
  return s - Math.floor(s)
}

function ci(mean: number, sigma: number): CI {
  return {
    mean: Number(mean.toFixed(3)),
    lo_95: Number((mean - 1.96 * sigma).toFixed(3)),
    hi_95: Number((mean + 1.96 * sigma).toFixed(3)),
  }
}

function buildLap(lapNum: number): LapData {
  const age = lapNum - 1
  const h = hash(lapNum)
  const degradation = age * 0.0015
  const baseGrip = 0.92 - degradation
  const baseLapTime = 92.5 + age * 0.07 + (h - 0.5) * 0.3
  const baseTemp = 85 + age * 0.4 + (h - 0.5) * 3

  return {
    lap_number: lapNum,
    stint_age: age,
    lap_time: ci(baseLapTime, 0.12),
    sliding_power_total: ci(18500 + age * 120 + (hash(lapNum + 100) - 0.5) * 800, 320),
    t_tread_fl: ci(baseTemp + hash(lapNum + 10) * 6, 1.8),
    t_tread_fr: ci(baseTemp + hash(lapNum + 20) * 6 + 2, 1.8),
    t_tread_rl: ci(baseTemp + hash(lapNum + 30) * 6 + 1, 1.8),
    t_tread_rr: ci(baseTemp + hash(lapNum + 40) * 6 + 3, 1.8),
    grip_fl: ci(baseGrip - hash(lapNum + 50) * 0.02, 0.012),
    grip_fr: ci(baseGrip - hash(lapNum + 60) * 0.02, 0.012),
    grip_rl: ci(baseGrip - hash(lapNum + 70) * 0.02, 0.012),
    grip_rr: ci(baseGrip - hash(lapNum + 80) * 0.02, 0.012),
    e_tire_fl: ci(age * 0.18 + hash(lapNum + 90) * 0.05, 0.015),
    e_tire_fr: ci(age * 0.18 + hash(lapNum + 100) * 0.05, 0.015),
    e_tire_rl: ci(age * 0.18 + hash(lapNum + 110) * 0.05, 0.015),
    e_tire_rr: ci(age * 0.18 + hash(lapNum + 120) * 0.05, 0.015),
    slip_angle_fl: ci(1.8 + hash(lapNum + 130) * 0.4, 0.08),
    slip_angle_fr: ci(1.8 + hash(lapNum + 140) * 0.4, 0.08),
    slip_angle_rl: ci(1.8 + hash(lapNum + 150) * 0.4, 0.08),
    slip_angle_rr: ci(1.8 + hash(lapNum + 160) * 0.4, 0.08),
  }
}

const laps: LapData[] = Array.from({ length: 22 }, (_, i) => buildLap(i + 1))

export const BAHRAIN_LEC_S1: SimulationResult = {
  meta: {
    race: {
      id: '2024_bahrain',
      name: 'Bahrain Grand Prix',
      round: 1,
      season: 2024,
      circuit: 'Bahrain International Circuit',
    },
    driver: {
      code: 'LEC',
      number: 16,
      name: 'C. Leclerc',
      team: 'Ferrari',
      teamColor: '#DC0000',
    },
    stint: {
      id: 1,
      compound: 'MEDIUM',
      compoundColor: '#FFD700',
      startLap: 1,
      endLap: 22,
      lapCount: 22,
      startAge: 0,
    },
    calibration_id: 1,
    model_schema_version: '1.0.0',
    fastf1_version: '3.8.2',
    run_id: 'fixture-bahrain-lec-s1',
  },
  laps,
  track: [
    [0.5, 0.88],
    [0.55, 0.82],
    [0.62, 0.75],
    [0.7, 0.68],
    [0.78, 0.62],
    [0.84, 0.55],
    [0.88, 0.48],
    [0.85, 0.4],
    [0.78, 0.34],
    [0.7, 0.3],
    [0.62, 0.28],
    [0.52, 0.3],
    [0.44, 0.34],
    [0.38, 0.4],
    [0.32, 0.48],
    [0.3, 0.56],
    [0.34, 0.64],
    [0.4, 0.72],
    [0.44, 0.8],
    [0.5, 0.88],
  ],
  sectorBounds: [
    [0, 86],
    [86, 172],
    [172, 258],
  ],
  turns: [
    { n: 1, at: 0.05 },
    { n: 2, at: 0.08 },
    { n: 3, at: 0.12 },
    { n: 4, at: 0.18 },
    { n: 5, at: 0.24 },
    { n: 6, at: 0.32 },
    { n: 7, at: 0.38 },
    { n: 8, at: 0.44 },
    { n: 9, at: 0.5 },
    { n: 10, at: 0.55 },
    { n: 11, at: 0.62 },
    { n: 12, at: 0.68 },
    { n: 13, at: 0.75 },
    { n: 14, at: 0.82 },
    { n: 15, at: 0.88 },
  ],
}
