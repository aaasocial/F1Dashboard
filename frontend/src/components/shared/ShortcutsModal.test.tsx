import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { ShortcutsModal } from './ShortcutsModal'
import { useUIStore } from '../../stores/useUIStore'

beforeEach(() => {
  useUIStore.setState({
    hoveredLap: null, hoveredCorner: null, mode: 'live',
    playing: true, pos: 1.0, speed: 1,
    statusLogCollapsed: false, xZoom: null, mapFullscreen: false,
    shortcutsOpen: false, provenanceOpen: false, toastMessage: null,
  })
  cleanup()
})

describe('ShortcutsModal', () => {
  it('returns null when shortcutsOpen=false', () => {
    const { container } = render(<ShortcutsModal />)
    expect(container.firstChild).toBeNull()
  })

  it('renders when shortcutsOpen=true', () => {
    useUIStore.setState({ shortcutsOpen: true })
    render(<ShortcutsModal />)
    expect(screen.getByTestId('shortcuts-modal')).toBeTruthy()
  })

  it('renders at least 10 keyboard rows (Space, arrows, Home/End, corners, T, E, S, ?, Esc)', () => {
    useUIStore.setState({ shortcutsOpen: true })
    render(<ShortcutsModal />)
    const rows = screen.getByTestId('shortcuts-modal').querySelectorAll('tbody tr')
    expect(rows.length).toBeGreaterThanOrEqual(10)
  })

  it('calls setShortcutsOpen(false) on backdrop click', () => {
    useUIStore.setState({ shortcutsOpen: true })
    render(<ShortcutsModal />)
    const modal = screen.getByTestId('shortcuts-modal')
    fireEvent.click(modal)
    expect(useUIStore.getState().shortcutsOpen).toBe(false)
  })

  it('does NOT close when inner content is clicked (stopPropagation)', () => {
    useUIStore.setState({ shortcutsOpen: true })
    render(<ShortcutsModal />)
    const content = screen.getByTestId('shortcuts-modal-content')
    fireEvent.click(content)
    expect(useUIStore.getState().shortcutsOpen).toBe(true)
  })
})
