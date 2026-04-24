import { http, HttpResponse } from 'msw'

const RACES_FIXTURE = [
  {
    id: '2024_bahrain',
    name: 'Bahrain Grand Prix',
    round: 1,
    season: 2024,
    circuit: 'Bahrain International Circuit',
  },
]

const DRIVERS_FIXTURE = [
  { code: 'LEC', name: 'C. Leclerc', team: 'Ferrari', teamColor: '#DC0000' },
]

const STINTS_FIXTURE = [
  { id: 1, compound: 'MEDIUM', startLap: 1, endLap: 22, lapCount: 22, startAge: 0 },
]

const MODULES = [
  'Kinematics',
  'Load Transfer',
  'Slip & Contact',
  'Force Generation',
  'Thermal',
  'Wear & Grip Evolution',
  'Monte Carlo Roll-up',
]

export const handlers = [
  http.get('/api/races', () => HttpResponse.json(RACES_FIXTURE)),
  http.get('/api/races/:raceId/drivers', () => HttpResponse.json(DRIVERS_FIXTURE)),
  http.get('/api/stints/:raceId/:driverCode', () => HttpResponse.json(STINTS_FIXTURE)),
  http.post('/api/simulate/stream', async () => {
    const stream = new ReadableStream({
      async start(controller) {
        for (let i = 0; i < 7; i++) {
          await new Promise((r) => setTimeout(r, 10))
          const evt = `event: module_complete\ndata: ${JSON.stringify({
            module: i + 1,
            name: MODULES[i],
            lap_count: 22,
          })}\n\n`
          controller.enqueue(new TextEncoder().encode(evt))
        }
        // Final event: minimal valid SimulationResult in FRONTEND shape (after mapper)
        // Fields: meta (not metadata), laps (not per_lap), plus track/sectorBounds/turns
        const finalEvt = `event: simulation_complete\ndata: ${JSON.stringify({
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
            run_id: 'test',
          },
          laps: [],
          track: [[0.5, 0.88]],
          sectorBounds: [
            [0, 86],
            [86, 172],
            [172, 258],
          ],
          turns: [{ n: 1, at: 0.13 }],
        })}\n\n`
        controller.enqueue(new TextEncoder().encode(finalEvt))
        controller.close()
      },
    })
    return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
  }),
]
