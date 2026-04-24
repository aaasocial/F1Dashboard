import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MapFullscreenOverlay } from './MapFullscreenOverlay'
import { useUIStore } from '../../stores/useUIStore'
import { useSimulationStore } from '../../stores/useSimulationStore'

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
  useSimulationStore.setState({ data: null, loading: false, error: null, moduleProgress: null })
  cleanup()
})

describe('MapFullscreenOverlay', () => {
  it('returns null when mapFullscreen=false', () => {
    const { container } = render(<MapFullscreenOverlay />)
    expect(container.firstChild).toBeNull()
  })

  it('renders overlay container when mapFullscreen=true', () => {
    useUIStore.setState({ mapFullscreen: true })
    render(<MapFullscreenOverlay />)
    expect(screen.getByTestId('map-fullscreen')).toBeTruthy()
  })

  it('renders MapPanel inside the overlay (skeleton visible when no data)', () => {
    useUIStore.setState({ mapFullscreen: true })
    render(<MapFullscreenOverlay />)
    // MapPanel renders skeleton text when data is null
    expect(screen.getByText(/MAP — SELECT STINT AND RUN MODEL/)).toBeTruthy()
  })

  it('overlay has role=dialog for accessibility', () => {
    useUIStore.setState({ mapFullscreen: true })
    render(<MapFullscreenOverlay />)
    expect(screen.getByRole('dialog')).toBeTruthy()
  })
})
