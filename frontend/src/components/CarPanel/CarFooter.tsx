import { useUIStore } from '../../stores/useUIStore'
import { copyTireMetrics } from '../../lib/tireClipboard'
import type { LapData, Corner } from '../../lib/types'

const CORNERS: Corner[] = ['fl', 'fr', 'rl', 'rr']

function brakeTemp(lap: LapData, corner: Corner): number {
  const e = lap[`e_tire_${corner}` as keyof LapData] as { mean: number }
  const sl = lap[`slip_angle_${corner}` as keyof LapData] as { mean: number }
  const isFront = corner.startsWith('f')
  return (isFront ? 560 : 410) + e.mean * 22 + sl.mean * 28
}

function wearPct(lap: LapData, corner: Corner): number {
  const e = lap[`e_tire_${corner}` as keyof LapData] as { mean: number }
  return Math.max(0, Math.min(1, e.mean / 22))
}

interface CarFooterProps {
  lap: LapData | null
}

export function CarFooter({ lap }: CarFooterProps) {
  const hoveredCorner = useUIStore(s => s.hoveredCorner)
  const setHoveredCorner = useUIStore(s => s.setHoveredCorner)

  return (
    <div style={{
      borderTop: '1px solid var(--rule)',
      background: 'var(--panel-header)',
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 1,
    }}>
      {CORNERS.map(c => {
        const active = hoveredCorner === c
        const temp = lap ? lap[`t_tread_${c}` as keyof LapData] as { mean: number; lo_95: number; hi_95: number } : undefined
        const grip = lap ? lap[`grip_${c}` as keyof LapData] as { mean: number; lo_95: number; hi_95: number } : undefined
        const slip = lap ? lap[`slip_angle_${c}` as keyof LapData] as { mean: number; lo_95: number; hi_95: number } : undefined
        const wear = lap ? wearPct(lap, c) : 0
        const br = lap ? brakeTemp(lap, c) : 0
        const gripCi = grip ? (grip.hi_95 - grip.mean) : 0
        const wearColor = wear > 0.7 ? '#FF3344' : wear > 0.45 ? '#FFB020' : 'var(--text)'
        const cornerLabel = c.toUpperCase()
        const axleLabel = `${c.startsWith('f') ? 'FRONT' : 'REAR'}·${c.endsWith('l') ? 'L' : 'R'}`

        return (
          <div
            key={c}
            onMouseEnter={() => setHoveredCorner(c)}
            onMouseLeave={() => setHoveredCorner(null)}
            onContextMenu={(e) => {
              e.preventDefault()
              if (lap) void copyTireMetrics(c, lap)
            }}
            style={{
              padding: '8px 10px 10px',
              background: active ? 'var(--panel-header-hi)' : 'transparent',
              borderLeft: active ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer',
              fontFamily: 'var(--mono)',
            }}
          >
            {/* Corner label */}
            <div style={{
              display: 'flex', alignItems: 'baseline', gap: 6,
              marginBottom: 4,
            }}>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: 2,
                color: active ? 'var(--accent)' : 'var(--text)',
              }}>{cornerLabel}</span>
              <span style={{ fontSize: 8, color: 'var(--text-muted)', letterSpacing: 1 }}>
                {axleLabel}
              </span>
            </div>
            {/* T row */}
            <CarRow
              label="T"
              value={temp ? temp.mean.toFixed(1) : '—'}
              unit="°C"
              ci={temp ? `${temp.lo_95.toFixed(0)}–${temp.hi_95.toFixed(0)}` : undefined}
            />
            {/* μ row */}
            <CarRow
              label="μ"
              value={grip ? grip.mean.toFixed(3) : '—'}
              unit=""
              ci={grip ? `±${gripCi.toFixed(3)}` : undefined}
              valueColor="var(--accent)"
            />
            {/* WEAR row */}
            <CarRow
              label="WEAR"
              value={`${(wear * 100).toFixed(1)}`}
              unit="%"
              valueColor={wearColor}
            />
            {/* α row */}
            <CarRow
              label="α"
              value={slip ? slip.mean.toFixed(2) : '—'}
              unit="°"
            />
            {/* BRK row */}
            <CarRow
              label="BRK"
              value={lap ? br.toFixed(0) : '—'}
              unit="°C"
              valueColor="#FFB020"
            />
          </div>
        )
      })}
    </div>
  )
}

interface CarRowProps {
  label: string
  value: string
  unit: string
  ci?: string
  valueColor?: string
}

function CarRow({ label, value, unit, ci, valueColor = 'var(--text)' }: CarRowProps) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '28px 1fr',
      fontSize: 10, marginTop: 1, alignItems: 'baseline',
    }}>
      <span style={{ color: 'var(--text-muted)', letterSpacing: 1 }}>{label}</span>
      <span style={{ color: valueColor, textAlign: 'right', fontWeight: 600 }}>
        {value}
        <span style={{ color: 'var(--text-muted)', fontSize: 8, marginLeft: 2, fontWeight: 400 }}>
          {unit}
        </span>
        {ci && (
          <span style={{ color: 'var(--text-muted)', fontSize: 8, marginLeft: 4, fontWeight: 400 }}>
            {ci}
          </span>
        )}
      </span>
    </div>
  )
}
