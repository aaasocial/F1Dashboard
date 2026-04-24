import type { SimulateApiResponse, SimulationResult, SimulationMeta } from './types'
import { useSimulationStore } from '../stores/useSimulationStore'
import { useUIStore } from '../stores/useUIStore'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

/**
 * mapApiResponseToSimulationResult — Blocker 1 fix
 *
 * Transforms the raw backend SimulateApiResponse (Python field names, flat metadata)
 * into the frontend SimulationResult type (camelCase, structured meta).
 *
 * Field mappings:
 *   raw.metadata      → result.meta         (structured SimulationMeta)
 *   raw.per_lap       → result.laps         (LapData[])
 *   raw.track         → result.track        ([number,number][])
 *   raw.sector_bounds → result.sectorBounds ([number,number][])
 *   raw.turns         → result.turns        ({n,at}[])
 */
export function mapApiResponseToSimulationResult(raw: SimulateApiResponse): SimulationResult {
  const md = raw.metadata

  // Reconstruct SimulationMeta from the flat metadata block
  // Backend metadata fields vary by schema version; use safe fallbacks
  const meta: SimulationMeta = {
    race: {
      id: (md as Record<string, unknown>)['race_id'] as string ?? '',
      name: (md as Record<string, unknown>)['race_name'] as string ?? '',
      round: (md as Record<string, unknown>)['round'] as number ?? 0,
      season: (md as Record<string, unknown>)['season'] as number ?? 0,
      circuit: (md as Record<string, unknown>)['circuit'] as string ?? '',
    },
    driver: {
      code: (md as Record<string, unknown>)['driver_code'] as string ?? '',
      number: (md as Record<string, unknown>)['driver_number'] as number ?? 0,
      name: (md as Record<string, unknown>)['driver_name'] as string ?? '',
      team: (md as Record<string, unknown>)['team'] as string ?? '',
      teamColor: (md as Record<string, unknown>)['team_color'] as string ?? '#999999',
    },
    stint: {
      id: (md as Record<string, unknown>)['stint_index'] as number ?? 1,
      compound: md.compound ?? 'UNKNOWN',
      compoundColor: (md as Record<string, unknown>)['compound_color'] as string ?? '#999999',
      startLap: (md as Record<string, unknown>)['start_lap'] as number ?? 1,
      endLap: (md as Record<string, unknown>)['end_lap'] as number ?? 1,
      lapCount: raw.lap_count ?? raw.per_lap.length,
      startAge: (md as Record<string, unknown>)['start_age'] as number ?? 0,
    },
    calibration_id: md.calibration_id,
    model_schema_version: md.model_schema_version,
    fastf1_version: md.fastf1_version,
    run_id: (md as Record<string, unknown>)['run_id'] as string ?? '',
  }

  return {
    meta,
    laps: raw.per_lap,
    track: raw.track ?? [],
    sectorBounds: raw.sector_bounds ?? [],
    turns: raw.turns ?? [],
  }
}

export async function runSimulationStream(
  raceId: string,
  driverCode: string,
  stintIndex: number,
  signal: AbortSignal
): Promise<void> {
  const { setLoading, setError, setModuleProgress, setSimulationData } =
    useSimulationStore.getState()
  const { seek } = useUIStore.getState()

  setLoading(true)
  setError(null)

  try {
    const response = await fetch(`${API_BASE}/api/simulate/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ race_id: raceId, driver_code: driverCode, stint_index: stintIndex }),
      signal,
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    if (!response.body) throw new Error('No response body')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      let eventType = ''
      let dataLine = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) eventType = line.slice(7).trim()
        else if (line.startsWith('data: ')) dataLine = line.slice(6).trim()
        else if (line === '' && dataLine) {
          const payload = JSON.parse(dataLine) as Record<string, unknown>
          if (eventType === 'module_complete') {
            setModuleProgress({
              module: payload['module'] as number,
              name: payload['name'] as string,
              lap_count: payload['lap_count'] as number ?? 0,
            })
          } else if (eventType === 'simulation_complete') {
            // MSW mock sends frontend SimulationResult shape directly (bypasses mapper)
            // Real backend sends raw SimulateApiResponse that needs mapping
            // Detect by checking for 'meta' (frontend shape) vs 'metadata' (backend shape)
            if ('meta' in payload) {
              // Frontend shape from MSW mock — use directly
              setSimulationData(payload as unknown as SimulationResult)
            } else {
              // Backend shape — map via mapper
              const raw = payload as unknown as SimulateApiResponse
              const mapped = mapApiResponseToSimulationResult(raw)
              setSimulationData(mapped)
            }
            seek(1.0)  // reset playhead to lap 1 when new simulation arrives
          } else if (eventType === 'simulation_error') {
            setError((payload['error'] as string) ?? 'Simulation failed')
          }
          eventType = ''
          dataLine = ''
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      setError((err as Error).message)
    }
  } finally {
    setLoading(false)
    setModuleProgress(null)
  }
}
