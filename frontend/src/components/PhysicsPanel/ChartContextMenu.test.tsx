import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { ChartContextMenu } from './ChartContextMenu'

describe('ChartContextMenu', () => {
  afterEach(() => cleanup())

  it('returns null when open=false', () => {
    const { container } = render(
      <ChartContextMenu open={false} x={0} y={0} onExport={() => {}} onClose={() => {}} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders three menu items when open=true', () => {
    render(<ChartContextMenu open={true} x={50} y={50} onExport={() => {}} onClose={() => {}} />)
    expect(screen.getByText('Export PNG')).toBeTruthy()
    expect(screen.getByText('Export SVG')).toBeTruthy()
    expect(screen.getByText('Export CSV')).toBeTruthy()
  })

  it('clicking csv item calls onExport("csv")', () => {
    const onExport = vi.fn()
    render(<ChartContextMenu open={true} x={50} y={50} onExport={onExport} onClose={() => {}} />)
    fireEvent.click(screen.getByText('Export CSV'))
    expect(onExport).toHaveBeenCalledWith('csv')
  })

  it('clicking png item calls onExport("png")', () => {
    const onExport = vi.fn()
    render(<ChartContextMenu open={true} x={50} y={50} onExport={onExport} onClose={() => {}} />)
    fireEvent.click(screen.getByText('Export PNG'))
    expect(onExport).toHaveBeenCalledWith('png')
  })

  it('clamps position so menu does not overflow viewport', () => {
    const oldW = window.innerWidth
    Object.defineProperty(window, 'innerWidth', { value: 200, configurable: true })
    render(<ChartContextMenu open={true} x={500} y={50} onExport={() => {}} onClose={() => {}} />)
    const menu = screen.getByTestId('chart-context-menu')
    // 200 - 160 - 8 = 32
    expect(menu.style.left).toBe('32px')
    Object.defineProperty(window, 'innerWidth', { value: oldW, configurable: true })
  })

  it('Esc keydown calls onClose', () => {
    const onClose = vi.fn()
    render(<ChartContextMenu open={true} x={50} y={50} onExport={() => {}} onClose={onClose} />)
    fireEvent.keyDown(document, { code: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('mousedown outside calls onClose', () => {
    const onClose = vi.fn()
    render(<ChartContextMenu open={true} x={50} y={50} onExport={() => {}} onClose={onClose} />)
    fireEvent.mouseDown(document.body)
    expect(onClose).toHaveBeenCalled()
  })
})
