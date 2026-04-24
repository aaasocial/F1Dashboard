import { useState } from 'react'
import { useSimulationStore } from '../../stores/useSimulationStore'
import { useUIStore } from '../../stores/useUIStore'
import { PanelHeader } from '../shared/PanelHeader'
import { PanelSkeleton } from '../shared/Skeleton'
import { PhysicsChart } from './PhysicsChart'
import type { Corner } from '../../lib/types'

type MetricKey = 't_tread' | 'grip' | 'e_tire' | 'slip_angle'

interface MetricConfig {
  label: string
  unit: string
  fmt: (v: number) => string
  domain: [number, number]
  accent: string
}

// EXACT from cockpit-physics.jsx METRICS constant — non-negotiable values
const METRICS: Record<MetricKey, MetricConfig> = {
  t_tread:    { label: 'TREAD TEMP',  unit: '°C', fmt: v => v.toFixed(1), domain: [88, 118], accent: '#FFD700' },
  grip:       { label: 'GRIP μ',      unit: '',   fmt: v => v.toFixed(3), domain: [1.10, 1.50], accent: '#00E5FF' },
  e_tire:     { label: 'WEAR E',      unit: 'MJ', fmt: v => v.toFixed(2), domain: [0, 22],    accent: '#FFB020' },
  slip_angle: { label: 'SLIP α PEAK', unit: '°',  fmt: v => v.toFixed(2), domain: [1.5, 5.5], accent: '#A855F7' },
}

const METRIC_KEYS = Object.keys(METRICS) as MetricKey[]
const CORNERS: Corner[] = ['fl', 'fr', 'rl', 'rr']

export function PhysicsPanel() {
  const [metric, setMetric] = useState<MetricKey>('t_tread')
  const data = useSimulationStore(s => s.data)
  const pos = useUIStore(s => s.pos)

  if (!data) return <PanelSkeleton label="PHYSICS — SELECT STINT AND RUN MODEL" />

  const maxLap = data.laps.length
  const lapIdx = Math.min(maxLap - 1, Math.max(0, Math.floor(pos - 1)))
  const revealedLaps = data.laps.slice(0, lapIdx + 1)

  const cfg = METRICS[metric]

  return (
    <div style={{
      height: '100%',
      display: 'grid',
      gridTemplateRows: '38px auto 1fr',
      minHeight: 0,
    }}>
      <PanelHeader
        title="PHYSICS"
        subtitle="LAP-BY-LAP · CI₉₅"
        right={<span>{revealedLaps.length}/{maxLap} LAPS</span>}
      />

      {/* Tab strip — 4 equal-flex buttons */}
      <div style={{
        display: 'flex',
        background: 'var(--panel-header)',
        borderBottom: '1px solid var(--rule)',
        flexShrink: 0,
      }}>
        {METRIC_KEYS.map(key => {
          const m = METRICS[key]
          const active = metric === key
          return (
            <button
              key={key}
              onClick={() => setMetric(key)}
              role="tab"
              aria-selected={active}
              style={{
                flex: 1,
                padding: '7px 10px',
                background: active ? 'var(--panel-header-hi)' : 'transparent',
                border: 'none',
                borderBottom: active ? `2px solid ${m.accent}` : '2px solid transparent',
                color: active ? 'var(--text)' : 'var(--text-dim)',
                fontFamily: 'var(--mono)',
                fontSize: 9.5,
                letterSpacing: 1.6,
                fontWeight: active ? 700 : 500,
                textAlign: 'left',
                cursor: 'pointer',
              }}
            >
              {m.label}
              {m.unit && (
                <span style={{ marginLeft: 6, color: 'var(--text-muted)', letterSpacing: 1, fontSize: 8 }}>
                  {m.unit}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* 4 stacked small-multiple charts — equal height, one per corner */}
      <div style={{
        display: 'grid',
        gridTemplateRows: 'repeat(4, 1fr)',
        minHeight: 0,
        overflow: 'hidden',
      }}
        role="tabpanel"
        aria-label={`${cfg.label} charts`}
      >
        {CORNERS.map((c, i) => (
          <PhysicsChart
            key={c}
            corner={c}
            metricKey={metric}
            cfg={cfg}
            revealedLaps={revealedLaps}
            isLast={i === CORNERS.length - 1}
            maxLap={maxLap}
          />
        ))}
      </div>
    </div>
  )
}
