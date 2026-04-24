import { useUIStore } from '../../stores/useUIStore'

interface ShortcutRow { key: string; description: string }
const ROWS: ShortcutRow[] = [
  { key: 'Space',          description: 'Play / Pause' },
  { key: '← / →',          description: 'Step −1 / +1 lap' },
  { key: 'Shift + ← / →',  description: 'Jump to start of previous / next sector' },
  { key: 'Home / End',     description: 'Jump to lap 1 / last lap' },
  { key: '1 / 2 / 3 / 4',  description: 'Focus FL / FR / RL / RR corner' },
  { key: 'T',              description: 'Toggle fullscreen track map' },
  { key: 'E',              description: 'Toggle status log' },
  { key: 'S',              description: 'Copy current URL to clipboard' },
  { key: '?',              description: 'Show this shortcuts overlay' },
  { key: 'Esc',            description: 'Close any open overlay or modal' },
]

export function ShortcutsModal() {
  const open = useUIStore(s => s.shortcutsOpen)
  const setOpen = useUIStore(s => s.setShortcutsOpen)
  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      data-testid="shortcuts-modal"
      onClick={() => setOpen(false)}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(5,7,11,0.85)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--mono)',
      }}
    >
      <div
        data-testid="shortcuts-modal-content"
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--rule-strong)',
          borderRadius: 0,
          padding: '24px 28px',
          minWidth: 480,
          color: 'var(--text)',
          fontFamily: 'var(--mono)',
          fontSize: 11,
          letterSpacing: 1.2,
        }}
      >
        <div style={{
          fontSize: 10, color: 'var(--accent)', letterSpacing: 2.4, fontWeight: 700,
          marginBottom: 16,
        }}>KEYBOARD SHORTCUTS</div>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <tbody>
            {ROWS.map(row => (
              <tr key={row.key}>
                <td style={{
                  padding: '5px 16px 5px 0',
                  color: 'var(--accent)',
                  fontWeight: 700,
                  whiteSpace: 'nowrap',
                }}>{row.key}</td>
                <td style={{ padding: '5px 0', color: 'var(--text-dim)' }}>{row.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{
          marginTop: 20, fontSize: 9, color: 'var(--text-muted)', letterSpacing: 1.4,
        }}>
          ESC OR CLICK OUTSIDE TO CLOSE
        </div>
      </div>
    </div>
  )
}
