import { useUIStore } from '../../stores/useUIStore'
import type { LapData, Corner } from '../../lib/types'

// Generate log events client-side from CI data thresholds
// Per 05-CONTEXT.md open question #3: events derived from CI data, not backend field
function generateEvents(laps: LapData[]): Array<{ lap: number; message: string; level: 'info' | 'warn' | 'critical' }> {
  const events: Array<{ lap: number; message: string; level: 'info' | 'warn' | 'critical' }> = []
  const corners: Corner[] = ['fl', 'fr', 'rl', 'rr']
  const cornerLabels: Record<Corner, string> = { fl: 'FL', fr: 'FR', rl: 'RL', rr: 'RR' }

  for (const lap of laps) {
    for (const c of corners) {
      const temp = lap[`t_tread_${c}` as keyof LapData] as { mean: number }
      const grip = lap[`grip_${c}` as keyof LapData] as { mean: number }
      const wear = lap[`e_tire_${c}` as keyof LapData] as { mean: number }

      if (temp.mean > 112) {
        events.push({ lap: lap.lap_number,
          message: `${cornerLabels[c]} approaching thermal limit (${temp.mean.toFixed(1)}°C)`,
          level: 'critical' })
      } else if (temp.mean > 106) {
        events.push({ lap: lap.lap_number,
          message: `${cornerLabels[c]} tire in operating window (${temp.mean.toFixed(1)}°C)`,
          level: 'info' })
      }
      if (grip.mean < 1.25) {
        events.push({ lap: lap.lap_number,
          message: `${cornerLabels[c]} grip approaching threshold (μ ${grip.mean.toFixed(3)})`,
          level: 'warn' })
      }
      if (wear.mean > 18) {
        events.push({ lap: lap.lap_number,
          message: `${cornerLabels[c]} high cumulative wear (${wear.mean.toFixed(1)} MJ)`,
          level: 'critical' })
      }
    }
  }

  return events.sort((a, b) => a.lap - b.lap)
}

interface StatusLogProps {
  laps: LapData[]
}

export function StatusLog({ laps }: StatusLogProps) {
  const collapsed = useUIStore(s => s.statusLogCollapsed)
  const toggleStatusLog = useUIStore(s => s.toggleStatusLog)
  const hoveredLap = useUIStore(s => s.hoveredLap)

  const events = generateEvents(laps)

  const levelColor = { info: 'var(--accent)', warn: 'var(--warn)', critical: 'var(--hot)' } as const

  return (
    <div style={{
      background: 'var(--panel-header)',
      borderTop: '1px solid var(--rule)',
      flexShrink: 0,
    }}>
      {/* Collapsible header */}
      <div
        onClick={toggleStatusLog}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 14px',
          height: 28,
          cursor: 'pointer',
          fontFamily: 'var(--mono)',
          fontSize: 9, letterSpacing: 2, color: 'var(--text-muted)',
          userSelect: 'none',
        }}
        role="button"
        aria-expanded={!collapsed}
        aria-label="Toggle status log"
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 2, height: 10, background: 'var(--accent)' }} />
          <span>STATUS LOG</span>
          <span style={{ color: 'var(--text-dim)' }}>&middot; {events.length} EVENTS</span>
        </div>
        <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{collapsed ? '▼' : '▲'}</span>
      </div>

      {/* Log entries — max-height CSS animation per D-07 */}
      <div
        data-testid="status-log-body"
        style={{
          maxHeight: collapsed ? 0 : 140,
          overflowY: collapsed ? 'hidden' : 'auto',
          borderTop: collapsed ? 'none' : '1px solid var(--rule)',
          transition: 'max-height 220ms ease-in-out',
        }}
      >
        {events.length === 0 ? (
          <div style={{ padding: '8px 14px', fontSize: 8, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
            NO EVENTS
          </div>
        ) : (
          events.map((evt, i) => {
            const active = hoveredLap === evt.lap
            return (
              <div key={i} style={{
                padding: '4px 14px 4px 16px',
                borderLeft: `2px solid ${active ? levelColor[evt.level] : 'transparent'}`,
                background: active ? 'var(--panel-header-hi)' : 'transparent',
                display: 'flex', alignItems: 'center', gap: 10,
                fontFamily: 'var(--mono)',
              }}>
                <span style={{ fontSize: 8, color: 'var(--text-muted)', minWidth: 28 }}>
                  L{String(evt.lap).padStart(2, '0')}
                </span>
                <span style={{ fontSize: 8, color: levelColor[evt.level], flex: 1 }}>
                  {evt.message}
                </span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
