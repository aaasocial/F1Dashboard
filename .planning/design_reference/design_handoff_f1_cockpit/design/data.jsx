/* global React */
// Mock simulation data for Bahrain GP — Charles Leclerc — Stint 1
// Following Phase 4 API schema: CI triplets {mean, lo_95, hi_95} at per-lap level.

const META = {
  race: { id: "2024_bahrain", name: "Bahrain Grand Prix", round: 1, season: 2024, circuit: "Bahrain International Circuit" },
  driver: { code: "LEC", number: 16, name: "Charles Leclerc", team: "Ferrari", teamColor: "#DC0000" },
  stint: { id: 1, compound: "MEDIUM", compoundColor: "#FFD700", startLap: 1, endLap: 22, lapCount: 22, startAge: 0 },
  calibration_id: "cal_2024_bahrain_v3",
  model_schema_version: "1.0.0",
  fastf1_version: "3.3.4",
  run_id: "sim_20260424_lec_bah_s1_a7f3",
  seed: 42,
  timestamp: "2026-04-24T14:22:18Z",
};

// Seeded-ish deterministic noise for reproducibility across reloads
function hash(n) {
  const s = Math.sin(n * 9301 + 49297) * 233280;
  return s - Math.floor(s);
}

// Build per-lap data. Laps 1..22.
function buildLaps() {
  const laps = [];
  const corners = ["fl", "fr", "rl", "rr"];

  for (let i = 0; i < 22; i++) {
    const lap = i + 1;
    const age = i; // stint age in laps
    // Base lap time: starts ~94.2s, degrades with wear, fuel burn compensates a bit
    const fuelEffect = -0.035 * (21 - i); // heavier earlier
    const wearEffect = 0.018 * age + 0.0008 * age * age;
    const noise = (hash(lap * 7) - 0.5) * 0.25;
    const lapTimeMean = 93.85 + fuelEffect + wearEffect + noise;
    const lapTimeSigma = 0.14 + 0.006 * age;

    // Tread temperatures (°C) — steady-state around 95-105°C, rears warmer, fronts vary with corner load
    // FL/FR asymmetry: Bahrain is right-heavy (long lefts), left tires hotter
    const tBase = {
      fl: 103 + 0.12 * age + 2.5 * Math.sin(age / 3) + (hash(lap + 11) - 0.5) * 3,
      fr: 98 + 0.09 * age + 2.0 * Math.sin(age / 3 + 0.5) + (hash(lap + 13) - 0.5) * 3,
      rl: 108 + 0.16 * age + 2.2 * Math.sin(age / 3 + 0.2) + (hash(lap + 17) - 0.5) * 3,
      rr: 105 + 0.14 * age + 1.8 * Math.sin(age / 3 + 0.7) + (hash(lap + 19) - 0.5) * 3,
    };

    // Grip coefficient — decays from ~1.45 to ~1.18 over stint
    const gBase = {
      fl: 1.44 - 0.011 * age + (hash(lap + 21) - 0.5) * 0.015,
      fr: 1.45 - 0.010 * age + (hash(lap + 23) - 0.5) * 0.015,
      rl: 1.42 - 0.013 * age + (hash(lap + 27) - 0.5) * 0.015,
      rr: 1.43 - 0.012 * age + (hash(lap + 29) - 0.5) * 0.015,
    };

    // Tread wear energy (MJ cumulative) — monotonic increase
    const eBase = {
      fl: 0.8 * age + 0.02 * age * age + (hash(lap + 31) - 0.5) * 0.3,
      fr: 0.7 * age + 0.018 * age * age + (hash(lap + 33) - 0.5) * 0.3,
      rl: 0.95 * age + 0.024 * age * age + (hash(lap + 37) - 0.5) * 0.3,
      rr: 0.88 * age + 0.022 * age * age + (hash(lap + 39) - 0.5) * 0.3,
    };

    // Slip angle peak (deg)
    const sBase = {
      fl: 3.2 + 0.04 * age + 0.8 * Math.sin(age / 2) + (hash(lap + 41) - 0.5) * 0.4,
      fr: 3.0 + 0.035 * age + 0.7 * Math.sin(age / 2 + 0.3) + (hash(lap + 43) - 0.5) * 0.4,
      rl: 2.8 + 0.05 * age + 0.6 * Math.sin(age / 2 + 0.5) + (hash(lap + 47) - 0.5) * 0.4,
      rr: 2.7 + 0.045 * age + 0.55 * Math.sin(age / 2 + 0.8) + (hash(lap + 49) - 0.5) * 0.4,
    };

    const ci = (mean, sigma) => ({
      mean: Number(mean.toFixed(3)),
      lo_95: Number((mean - 1.96 * sigma).toFixed(3)),
      hi_95: Number((mean + 1.96 * sigma).toFixed(3)),
    });

    const row = {
      lap_number: lap,
      stint_age: age,
      lap_time: ci(lapTimeMean, lapTimeSigma),
      sliding_power_total: ci(420 + 8 * age + (hash(lap + 53) - 0.5) * 30, 12 + 0.5 * age),
    };
    for (const c of corners) {
      row[`t_tread_${c}`] = ci(tBase[c], 1.4 + 0.08 * age);
      row[`grip_${c}`] = ci(gBase[c], 0.012 + 0.001 * age);
      row[`e_tire_${c}`] = ci(eBase[c], 0.15 + 0.02 * age);
      row[`slip_angle_${c}`] = ci(sBase[c], 0.18 + 0.01 * age);
    }
    laps.push(row);
  }
  return laps;
}

const LAPS = buildLaps();

// Bahrain International Circuit — stylized outline in [0,1] normalized coords.
// Traced approximately from the circuit layout. 120 points for smoothness.
function buildBahrainPath() {
  // Hand-placed waypoints for Bahrain (start/finish bottom-right, CCW... actually CW)
  // Bahrain runs clockwise. Waypoints approximate.
  const wp = [
    [0.50, 0.88], // start/finish straight
    [0.58, 0.88],
    [0.66, 0.87],
    [0.74, 0.84], // T1 braking
    [0.80, 0.78], // T1 apex
    [0.82, 0.72],
    [0.80, 0.66], // T2
    [0.74, 0.62], // T3
    [0.68, 0.60],
    [0.62, 0.58],
    [0.58, 0.54],
    [0.56, 0.48], // T4 long right
    [0.60, 0.42],
    [0.66, 0.38],
    [0.72, 0.34],
    [0.78, 0.30], // back straight start
    [0.82, 0.26],
    [0.84, 0.20],
    [0.82, 0.14], // T8 hairpin
    [0.76, 0.10],
    [0.68, 0.10],
    [0.60, 0.12],
    [0.52, 0.14],
    [0.44, 0.16],
    [0.36, 0.18],
    [0.28, 0.20],
    [0.22, 0.24], // T10
    [0.18, 0.30],
    [0.20, 0.36], // T11
    [0.26, 0.40],
    [0.30, 0.44],
    [0.28, 0.50], // T12/13 complex
    [0.22, 0.54],
    [0.16, 0.58],
    [0.12, 0.64],
    [0.14, 0.70], // T14
    [0.20, 0.74],
    [0.26, 0.76],
    [0.32, 0.78],
    [0.38, 0.82], // T15
    [0.42, 0.86],
    [0.46, 0.88],
    [0.50, 0.88], // close
  ];
  // Catmull-Rom smoothing
  const N = wp.length;
  const pts = [];
  const samples = 6;
  for (let i = 0; i < N; i++) {
    const p0 = wp[(i - 1 + N) % N];
    const p1 = wp[i];
    const p2 = wp[(i + 1) % N];
    const p3 = wp[(i + 2) % N];
    for (let t = 0; t < samples; t++) {
      const s = t / samples;
      const s2 = s * s;
      const s3 = s2 * s;
      const x = 0.5 * ((2 * p1[0]) +
        (-p0[0] + p2[0]) * s +
        (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * s2 +
        (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * s3);
      const y = 0.5 * ((2 * p1[1]) +
        (-p0[1] + p2[1]) * s +
        (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * s2 +
        (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * s3);
      pts.push([x, y]);
    }
  }
  return pts;
}

const TRACK_POINTS = buildBahrainPath();

// Sectors split by index bounds (roughly 3 equal portions)
const SECTOR_BOUNDS = [
  [0, Math.floor(TRACK_POINTS.length / 3)],
  [Math.floor(TRACK_POINTS.length / 3), Math.floor(2 * TRACK_POINTS.length / 3)],
  [Math.floor(2 * TRACK_POINTS.length / 3), TRACK_POINTS.length],
];

// Marshal posts / turn numbers (sparse)
const TURNS = [
  { n: 1, at: 0.13 },
  { n: 4, at: 0.26 },
  { n: 8, at: 0.42 },
  { n: 10, at: 0.58 },
  { n: 13, at: 0.72 },
  { n: 15, at: 0.88 },
];

// SSE Module schedule — matches physics model_v1
const MODULES = [
  { n: 1, name: "Kinematics", detail: "wheel speed · yaw rate · body velocity", ms: 520 },
  { n: 2, name: "Load Transfer", detail: "4-wheel vertical loads", ms: 680 },
  { n: 3, name: "Slip & Contact", detail: "slip angle · contact patch kinematics", ms: 740 },
  { n: 4, name: "Force Generation", detail: "Pacejka lateral/longitudinal", ms: 860 },
  { n: 5, name: "Thermal", detail: "tread / carcass / rim temperatures", ms: 920 },
  { n: 6, name: "Wear & Grip Evolution", detail: "abrasive + thermal wear", ms: 780 },
  { n: 7, name: "Monte Carlo Roll-up", detail: "500 samples · 95% CI", ms: 1100 },
];

// FIA compound colors
const COMPOUND_COLORS = {
  SOFT: "#FF3333",
  MEDIUM: "#FFD700",
  HARD: "#FFFFFF",
  INTER: "#22C55E",
  WET: "#3B82F6",
};

// Okabe-Ito colorblind-safe palette for corners
const CORNER_COLORS = {
  fl: "#E69F00", // orange
  fr: "#56B4E9", // sky
  rl: "#009E73", // teal-green
  rr: "#F0E442", // yellow
};
const CORNER_LABELS = { fl: "FL", fr: "FR", rl: "RL", rr: "RR" };

// Viridis-ish color scale (simplified) for temperature 60..120°C
const VIRIDIS = [
  [0.00, [68, 1, 84]],
  [0.13, [72, 35, 116]],
  [0.25, [64, 67, 135]],
  [0.38, [52, 94, 141]],
  [0.50, [41, 120, 142]],
  [0.63, [32, 144, 140]],
  [0.75, [34, 167, 132]],
  [0.88, [94, 201, 97]],
  [1.00, [253, 231, 37]],
];
function viridis(t) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < VIRIDIS.length; i++) {
    if (t <= VIRIDIS[i][0]) {
      const [t0, c0] = VIRIDIS[i - 1];
      const [t1, c1] = VIRIDIS[i];
      const u = (t - t0) / (t1 - t0);
      const r = Math.round(c0[0] + u * (c1[0] - c0[0]));
      const g = Math.round(c0[1] + u * (c1[1] - c0[1]));
      const b = Math.round(c0[2] + u * (c1[2] - c0[2]));
      return `rgb(${r},${g},${b})`;
    }
  }
  return "rgb(253,231,37)";
}
function tempToViridis(tempC) {
  return viridis((tempC - 60) / (120 - 60));
}

// Races available in cascade — 2024 F1 calendar
const RACES = [
  { id: "2024_bahrain",    name: "Bahrain GP",        round: 1,  circuit: "Bahrain International Circuit", laps: 57, km: 5.412 },
  { id: "2024_saudi",      name: "Saudi Arabian GP",  round: 2,  circuit: "Jeddah Corniche Circuit",       laps: 50, km: 6.174 },
  { id: "2024_australia",  name: "Australian GP",     round: 3,  circuit: "Albert Park Circuit",           laps: 58, km: 5.278 },
  { id: "2024_japan",      name: "Japanese GP",       round: 4,  circuit: "Suzuka Circuit",                laps: 53, km: 5.807 },
  { id: "2024_china",      name: "Chinese GP",        round: 5,  circuit: "Shanghai International Circuit",laps: 56, km: 5.451 },
  { id: "2024_miami",      name: "Miami GP",          round: 6,  circuit: "Miami International Autodrome", laps: 57, km: 5.412 },
  { id: "2024_emilia",     name: "Emilia-Romagna GP", round: 7,  circuit: "Imola Circuit",                 laps: 63, km: 4.909 },
  { id: "2024_monaco",     name: "Monaco GP",         round: 8,  circuit: "Circuit de Monaco",             laps: 78, km: 3.337 },
  { id: "2024_canada",     name: "Canadian GP",       round: 9,  circuit: "Circuit Gilles Villeneuve",     laps: 70, km: 4.361 },
  { id: "2024_spain",      name: "Spanish GP",        round: 10, circuit: "Circuit de Barcelona-Catalunya",laps: 66, km: 4.657 },
  { id: "2024_austria",    name: "Austrian GP",       round: 11, circuit: "Red Bull Ring",                 laps: 71, km: 4.318 },
  { id: "2024_britain",    name: "British GP",        round: 12, circuit: "Silverstone Circuit",           laps: 52, km: 5.891 },
  { id: "2024_hungary",    name: "Hungarian GP",      round: 13, circuit: "Hungaroring",                   laps: 70, km: 4.381 },
  { id: "2024_belgium",    name: "Belgian GP",        round: 14, circuit: "Circuit de Spa-Francorchamps",  laps: 44, km: 7.004 },
  { id: "2024_netherlands",name: "Dutch GP",          round: 15, circuit: "Circuit Zandvoort",             laps: 72, km: 4.259 },
  { id: "2024_italy",      name: "Italian GP",        round: 16, circuit: "Autodromo Nazionale Monza",     laps: 53, km: 5.793 },
  { id: "2024_azerbaijan", name: "Azerbaijan GP",     round: 17, circuit: "Baku City Circuit",             laps: 51, km: 6.003 },
  { id: "2024_singapore",  name: "Singapore GP",      round: 18, circuit: "Marina Bay Street Circuit",     laps: 62, km: 4.940 },
  { id: "2024_usa",        name: "United States GP",  round: 19, circuit: "Circuit of the Americas",       laps: 56, km: 5.513 },
  { id: "2024_mexico",     name: "Mexico City GP",    round: 20, circuit: "Autódromo Hermanos Rodríguez",  laps: 71, km: 4.304 },
  { id: "2024_brazil",     name: "São Paulo GP",      round: 21, circuit: "Interlagos",                    laps: 71, km: 4.309 },
  { id: "2024_vegas",      name: "Las Vegas GP",      round: 22, circuit: "Las Vegas Strip Circuit",       laps: 50, km: 6.201 },
  { id: "2024_qatar",      name: "Qatar GP",          round: 23, circuit: "Lusail International Circuit",  laps: 57, km: 5.419 },
  { id: "2024_abudhabi",   name: "Abu Dhabi GP",      round: 24, circuit: "Yas Marina Circuit",            laps: 58, km: 5.281 },
];

// 20-driver 2024 grid
const GRID = [
  { code: "VER", name: "M. Verstappen",     team: "Red Bull",   teamColor: "#3671C6" },
  { code: "PER", name: "S. Pérez",          team: "Red Bull",   teamColor: "#3671C6" },
  { code: "LEC", name: "C. Leclerc",        team: "Ferrari",    teamColor: "#DC0000" },
  { code: "SAI", name: "C. Sainz",          team: "Ferrari",    teamColor: "#DC0000" },
  { code: "HAM", name: "L. Hamilton",       team: "Mercedes",   teamColor: "#27F4D2" },
  { code: "RUS", name: "G. Russell",        team: "Mercedes",   teamColor: "#27F4D2" },
  { code: "NOR", name: "L. Norris",         team: "McLaren",    teamColor: "#FF8000" },
  { code: "PIA", name: "O. Piastri",        team: "McLaren",    teamColor: "#FF8000" },
  { code: "ALO", name: "F. Alonso",         team: "Aston Martin",teamColor: "#229971" },
  { code: "STR", name: "L. Stroll",         team: "Aston Martin",teamColor: "#229971" },
  { code: "GAS", name: "P. Gasly",          team: "Alpine",     teamColor: "#0093CC" },
  { code: "OCO", name: "E. Ocon",           team: "Alpine",     teamColor: "#0093CC" },
  { code: "ALB", name: "A. Albon",          team: "Williams",   teamColor: "#64C4FF" },
  { code: "SAR", name: "L. Sargeant",       team: "Williams",   teamColor: "#64C4FF" },
  { code: "TSU", name: "Y. Tsunoda",        team: "RB",         teamColor: "#6692FF" },
  { code: "RIC", name: "D. Ricciardo",      team: "RB",         teamColor: "#6692FF" },
  { code: "HUL", name: "N. Hülkenberg",     team: "Haas",       teamColor: "#B6BABD" },
  { code: "MAG", name: "K. Magnussen",      team: "Haas",       teamColor: "#B6BABD" },
  { code: "BOT", name: "V. Bottas",         team: "Sauber",     teamColor: "#52E252" },
  { code: "ZHO", name: "Zhou Guanyu",       team: "Sauber",     teamColor: "#52E252" },
];

// Every race gets the full 20-driver grid
const DRIVERS = Object.fromEntries(RACES.map(r => [r.id, GRID]));

// Typical 3-stint strategies per driver (deterministic by code hash)
function stintsFor(code) {
  const h = [...code].reduce((a, c) => a + c.charCodeAt(0), 0);
  const strategies = [
    [["MEDIUM", 22], ["HARD", 22], ["HARD", 13]],
    [["SOFT", 14], ["MEDIUM", 22], ["HARD", 21]],
    [["MEDIUM", 19], ["MEDIUM", 20], ["HARD", 18]],
    [["HARD", 28], ["MEDIUM", 16], ["SOFT", 13]],
    [["SOFT", 11], ["HARD", 28], ["HARD", 18]],
  ];
  const s = strategies[h % strategies.length];
  let lap = 1;
  return s.map((seg, i) => {
    const startLap = lap;
    lap += seg[1];
    return { id: i + 1, compound: seg[0], laps: `${startLap}–${lap - 1}`, lapCount: seg[1] };
  });
}
const STINTS = Object.fromEntries(GRID.map(d => [d.code, stintsFor(d.code)]));

// ──────────────────────────────────────────────────────────────────────────
// BACKEND SWAP POINT
// ──────────────────────────────────────────────────────────────────────────
// The UI fetches telemetry via F1Data.fetchTelemetry(). Today it returns the
// static Bahrain/LEC/Stint-1 fixture for every (race, driver, stint) combo.
// When you wire up a real backend, replace the body of this function with
// a fetch() call:
//
//   async function fetchTelemetry({ raceId, driverCode, stintIdx }) {
//     const r = await fetch(`/api/telemetry/${raceId}/${driverCode}/${stintIdx}`);
//     if (!r.ok) throw new Error(`HTTP ${r.status}`);
//     return await r.json();   // must return { meta, laps, track, sectorBounds, turns }
//   }
//
// The response schema the frontend expects:
//
//   meta:          { race:{id,name,round,season,circuit},
//                    driver:{code,number,name,team,teamColor},
//                    stint:{id,compound,compoundColor,startLap,endLap,lapCount,startAge},
//                    calibration_id, model_schema_version, fastf1_version,
//                    run_id, seed, timestamp }
//   laps:          Array<{ lap_number, stint_age, lap_time:{mean,lo_95,hi_95},
//                          sliding_power_total, t_tread_fl/fr/rl/rr:{mean,lo_95,hi_95},
//                          grip_fl/..., wear_fl/..., slip_peak_fl/...,
//                          brake_temp_fl/..., load_fl/... }>
//   track:         Array<[x,y]>  // closed polyline, 0..1 normalized
//   sectorBounds:  [n1, n2]      // indices into track[] dividing S1|S2|S3
//   turns:         Array<{ id, name, frac, apex:[x,y] }>
//
// The static data below is treated as a single-race-single-driver fixture.
// The dropdowns already pass the ids through; today we just ignore them and
// return the fixture. Swap this one function and the UI lights up with real
// data.
// ──────────────────────────────────────────────────────────────────────────

async function fetchTelemetry(params) {
  // Simulate network latency so loading states show up realistically.
  // Remove when the real endpoint is in.
  await new Promise(r => setTimeout(r, 220));

  // Re-label the fixture with the selected identity so the UI looks right.
  const race = RACES.find(r => r.id === params.raceId) || RACES[0];
  const driver = GRID.find(d => d.code === params.driverCode) || GRID[0];
  const stints = STINTS[driver.code] || STINTS.LEC;
  const stint = stints[Math.min(params.stintIdx ?? 0, stints.length - 1)] || stints[0];

  const [startLap, endLap] = stint.laps.split("–").map(Number);

  const meta = {
    race: {
      id: race.id, name: race.name, round: race.round,
      season: 2024, circuit: race.circuit,
    },
    driver: {
      code: driver.code, number: 0, name: driver.name,
      team: driver.team, teamColor: driver.teamColor,
    },
    stint: {
      id: stint.id,
      compound: stint.compound,
      compoundColor: COMPOUND_COLORS[stint.compound] || "#FFD700",
      startLap, endLap, lapCount: stint.lapCount, startAge: 0,
    },
    calibration_id: `cal_${race.id}_v3`,
    model_schema_version: "1.0.0",
    fastf1_version: "3.3.4",
    run_id: `sim_${race.id}_${driver.code}_s${stint.id}`,
    seed: 42,
    timestamp: new Date().toISOString(),
  };

  return {
    meta,
    laps: LAPS,                // FIXTURE — same series for every pick
    track: TRACK_POINTS,       // FIXTURE — Bahrain outline for every pick
    sectorBounds: SECTOR_BOUNDS,
    turns: TURNS,
  };
}

window.F1Data = {
  META, LAPS, TRACK_POINTS, SECTOR_BOUNDS, TURNS, MODULES,
  COMPOUND_COLORS, CORNER_COLORS, CORNER_LABELS,
  viridis, tempToViridis,
  RACES, DRIVERS, STINTS, GRID,
  fetchTelemetry,
};
