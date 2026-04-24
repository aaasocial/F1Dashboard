import { http, HttpResponse } from 'msw'
import { BAHRAIN_LEC_S1 } from './fixtures/bahrain-lec-s1'

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
        const finalEvt = `event: simulation_complete\ndata: ${JSON.stringify(BAHRAIN_LEC_S1)}\n\n`
        controller.enqueue(new TextEncoder().encode(finalEvt))
        controller.close()
      },
    })
    return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
  }),
  http.post('/api/sessions/upload', async () => {
    await new Promise(r => setTimeout(r, 80))
    return HttpResponse.json({ session_id: 'test-session-abc123' })
  }),
]
