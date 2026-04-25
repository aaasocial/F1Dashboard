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
  const baseGrip = 1.35 - degradation * 5  // domain [1.10, 1.50]: 1.35 fresh → ~1.19 at 22 laps
  const baseLapTime = 92.5 + age * 0.07 + (h - 0.5) * 0.3
  const baseTemp = 90 + age * 0.5 + (h - 0.5) * 4  // domain [88, 118]: starts above 88 floor

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
  // Approximate Bahrain International Circuit layout in normalized [0,1] SVG space.
  // 59 waypoints, clockwise. Real GPS coords come from FastF1 in production.
  track: [
    // S/F + main straight (northward, y decreasing)
    [0.70, 0.62], // 0  S/F
    [0.70, 0.57], // 1
    [0.70, 0.51], // 2
    [0.70, 0.45], // 3
    [0.70, 0.39], // 4
    [0.70, 0.33], // 5
    [0.70, 0.27], // 6
    // T1 hairpin (sharp right)
    [0.72, 0.22], // 7
    [0.76, 0.18], // 8
    [0.80, 0.15], // 9  T1 apex
    [0.84, 0.17], // 10
    [0.87, 0.20], // 11
    [0.86, 0.25], // 12
    [0.82, 0.27], // 13
    // T2 left
    [0.78, 0.27], // 14 T2
    [0.75, 0.28], // 15
    [0.73, 0.30], // 16
    // T3 slight right
    [0.74, 0.34], // 17 T3
    [0.74, 0.38], // 18
    [0.72, 0.41], // 19
    // T4 left hairpin (characteristic Bahrain turn)
    [0.68, 0.44], // 20 T4 entry
    [0.63, 0.46], // 21
    [0.57, 0.46], // 22 T4 apex
    [0.52, 0.43], // 23
    [0.51, 0.39], // 24 T5 right
    [0.53, 0.35], // 25
    [0.57, 0.33], // 26 T5 exit
    // back straight (westward)
    [0.53, 0.32], // 27
    [0.47, 0.32], // 28
    [0.41, 0.33], // 29
    [0.36, 0.34], // 30
    // T6 left
    [0.31, 0.37], // 31 T6
    [0.29, 0.41], // 32
    [0.31, 0.45], // 33
    // T7 right
    [0.35, 0.48], // 34 T7
    [0.37, 0.52], // 35
    // T8 left
    [0.34, 0.56], // 36 T8
    [0.31, 0.59], // 37
    [0.27, 0.62], // 38
    // T9 right (DRS detection zone)
    [0.25, 0.66], // 39 T9
    [0.26, 0.69], // 40
    [0.29, 0.71], // 41
    // T10 left
    [0.27, 0.74], // 42 T10
    [0.24, 0.76], // 43
    // T11 sweeping right → bottom straight
    [0.25, 0.79], // 44 T11
    [0.29, 0.82], // 45
    [0.35, 0.84], // 46
    [0.41, 0.84], // 47
    [0.47, 0.83], // 48
    // T12 right
    [0.53, 0.82], // 49 T12
    [0.57, 0.80], // 50
    [0.60, 0.77], // 51
    // T13 left
    [0.61, 0.73], // 52 T13
    [0.59, 0.70], // 53
    [0.56, 0.68], // 54
    // T14 right
    [0.58, 0.65], // 55 T14
    [0.62, 0.63], // 56
    [0.65, 0.62], // 57
    // T15 fast right → S/F
    [0.67, 0.62], // 58 T15
  ],
  // 59 points total; S1≈31%, S2≈40%, S3≈29% of lap
  sectorBounds: [
    [0, 18],
    [18, 43],
    [43, 58],
  ],
  turns: [
    { n: 1,  at: 0.15 },
    { n: 2,  at: 0.24 },
    { n: 3,  at: 0.29 },
    { n: 4,  at: 0.37 },
    { n: 5,  at: 0.41 },
    { n: 6,  at: 0.54 },
    { n: 7,  at: 0.58 },
    { n: 8,  at: 0.61 },
    { n: 9,  at: 0.66 },
    { n: 10, at: 0.71 },
    { n: 11, at: 0.75 },
    { n: 12, at: 0.83 },
    { n: 13, at: 0.88 },
    { n: 14, at: 0.93 },
    { n: 15, at: 0.98 },
  ],
}
