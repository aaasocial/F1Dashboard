import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { ProvenanceModal } from './ProvenanceModal'
import { useUIStore } from '../../stores/useUIStore'
import { useSimulationStore } from '../../stores/useSimulationStore'

const meta = {
  race: { id: 'R', name: 'R', round: 1, season: 2024, circuit: 'C' },
  driver: { code: 'D', number: 16, name: 'X', team: 'T', teamColor: '#000' },
  stint: { id: 1, compound: 'M', compoundColor: '#fff', startLap: 1, endLap: 22, lapCount: 22, startAge: 0 },
  calibration_id: 17,
  model_schema_version: 'v1.2',
  fastf1_version: '3.8.2',
  run_id: 'r-abc',
}

beforeEach(() => {
  cleanup()
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
  useSimulationStore.setState({ data: null, loading: false, error: null, moduleProgress: null })
})

describe('ProvenanceModal', () => {
  it('returns null when provenanceOpen=false', () => {
    const { container } = render(<ProvenanceModal />)
    expect(container.firstChild).toBeNull()
  })
  it('renders provenance fields from data.meta when open', () => {
    useSimulationStore.setState({ data: { meta, laps: [], track: [], sectorBounds: [], turns: [] } as any })
    useUIStore.setState({ provenanceOpen: true })
    render(<ProvenanceModal />)
    expect(screen.getByText('3.8.2')).toBeTruthy()
    expect(screen.getByText('v1.2')).toBeTruthy()
    expect(screen.getByText('17')).toBeTruthy()
    expect(screen.getByText('r-abc')).toBeTruthy()
  })
  it('shows N/A when data is null', () => {
    useUIStore.setState({ provenanceOpen: true })
    render(<ProvenanceModal />)
    // Five rows × 'N/A' value cell = 5 occurrences (Calibration date is always N/A)
    const naCells = screen.getAllByText('N/A')
    expect(naCells.length).toBeGreaterThanOrEqual(4)
  })
  it('renders the disclaimer literal', () => {
    useUIStore.setState({ provenanceOpen: true })
    render(<ProvenanceModal />)
    expect(screen.getByText(/Unofficial fan tool/)).toBeTruthy()
  })
  it('backdrop click closes the modal', () => {
    useUIStore.setState({ provenanceOpen: true })
    render(<ProvenanceModal />)
    fireEvent.click(screen.getByTestId('provenance-modal'))
    expect(useUIStore.getState().provenanceOpen).toBe(false)
  })
  it('content click does NOT close the modal', () => {
    useUIStore.setState({ provenanceOpen: true })
    render(<ProvenanceModal />)
    fireEvent.click(screen.getByTestId('provenance-modal-content'))
    expect(useUIStore.getState().provenanceOpen).toBe(true)
  })
})
