import { describe, it, expect, beforeEach } from 'vitest'
import { render, act, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from './App'
import { useUIStore } from './stores/useUIStore'
import { useSimulationStore } from './stores/useSimulationStore'

function renderApp() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>
  )
}

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: false, pos: 5.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
  useSimulationStore.setState({ data: null, loading: false, error: null, moduleProgress: null })
  cleanup()
})

describe('App keyboard integration', () => {
  it('dispatching Space keydown on document toggles playing', () => {
    renderApp()
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space', bubbles: true, cancelable: true }))
    })
    // playing was false, Space should toggle to true
    expect(useUIStore.getState().playing).toBe(true)
  })

  it('dispatching ArrowRight on document advances pos', () => {
    renderApp()
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { code: 'ArrowRight', shiftKey: false, bubbles: true, cancelable: true }))
    })
    // pos was 5, ArrowRight → 6
    expect(useUIStore.getState().pos).toBe(6)
  })
})

describe('App renders Toast when toastMessage is set', () => {
  it('renders toast when toastMessage is non-null', () => {
    useUIStore.setState({ toastMessage: 'URL COPIED' })
    const { getByTestId } = renderApp()
    expect(getByTestId('toast')).toBeTruthy()
  })

  it('does not render toast when toastMessage is null', () => {
    useUIStore.setState({ toastMessage: null })
    const { queryByTestId } = renderApp()
    expect(queryByTestId('toast')).toBeNull()
  })
})

describe('App renders overlay components', () => {
  it('renders ShortcutsModal when shortcutsOpen=true', () => {
    useUIStore.setState({ shortcutsOpen: true })
    const { getByTestId } = renderApp()
    expect(getByTestId('shortcuts-modal')).toBeTruthy()
  })

  it('renders MapFullscreenOverlay when mapFullscreen=true', () => {
    useUIStore.setState({ mapFullscreen: true })
    const { getByTestId } = renderApp()
    expect(getByTestId('map-fullscreen')).toBeTruthy()
  })
})
