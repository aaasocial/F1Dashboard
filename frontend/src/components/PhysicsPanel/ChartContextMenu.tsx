import { useEffect, useRef } from 'react'

export type ExportFormat = 'png' | 'svg' | 'csv'

interface ChartContextMenuProps {
  open: boolean
  x: number          // clientX
  y: number          // clientY
  onExport: (format: ExportFormat) => void
  onClose: () => void
}

const MENU_W = 160
const MENU_H = 110

export function ChartContextMenu({ open, x, y, onExport, onClose }: ChartContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null)

  // Click-outside / Esc / scroll dismiss
  useEffect(() => {
    if (!open) return
    function onMousedown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    function onKeydown(e: KeyboardEvent) {
      if (e.code === 'Escape') onClose()
    }
    function onScroll() { onClose() }
    function onResize() { onClose() }
    document.addEventListener('mousedown', onMousedown)
    document.addEventListener('keydown', onKeydown)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onResize)
    return () => {
      document.removeEventListener('mousedown', onMousedown)
      document.removeEventListener('keydown', onKeydown)
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onResize)
    }
  }, [open, onClose])

  if (!open) return null

  // Clamp to viewport
  const left = Math.min(x, window.innerWidth - MENU_W - 8)
  const top = Math.min(y, window.innerHeight - MENU_H - 8)

  const itemStyle: React.CSSProperties = {
    display: 'block',
    width: '100%',
    padding: '7px 14px',
    background: 'transparent',
    border: 'none',
    color: 'var(--text)',
    fontFamily: 'var(--mono)',
    fontSize: 11,
    letterSpacing: 1.4,
    textAlign: 'left',
    cursor: 'pointer',
    borderRadius: 0,
  }

  return (
    <div
      ref={ref}
      role="menu"
      data-testid="chart-context-menu"
      style={{
        position: 'fixed',
        left,
        top,
        width: MENU_W,
        background: 'var(--panel)',
        border: '1px solid var(--rule-strong)',
        borderRadius: 0,
        zIndex: 150,
        fontFamily: 'var(--mono)',
        boxShadow: '0 4px 18px rgba(0,0,0,0.55)',
      }}
    >
      <button role="menuitem" data-export="png" onClick={() => onExport('png')} style={itemStyle}
        onMouseEnter={e => (e.currentTarget.style.background = 'var(--panel-header-hi)')}
        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
      >Export PNG</button>
      <button role="menuitem" data-export="svg" onClick={() => onExport('svg')} style={itemStyle}
        onMouseEnter={e => (e.currentTarget.style.background = 'var(--panel-header-hi)')}
        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
      >Export SVG</button>
      <button role="menuitem" data-export="csv" onClick={() => onExport('csv')} style={itemStyle}
        onMouseEnter={e => (e.currentTarget.style.background = 'var(--panel-header-hi)')}
        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
      >Export CSV</button>
    </div>
  )
}
