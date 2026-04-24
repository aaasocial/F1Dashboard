import { useSimulationStore } from '../../stores/useSimulationStore'
import { useUIStore } from '../../stores/useUIStore'
import { PanelHeader } from '../shared/PanelHeader'
import { PanelSkeleton } from '../shared/Skeleton'
import { CarChassis } from './CarChassis'
import { CarWheel } from './CarWheel'
import { CarFooter } from './CarFooter'
import { compoundColor } from '../../lib/scales'
import type { Corner } from '../../lib/types'

const CAR_W = 400
const CAR_H = 780

const TIRES = {
  fl: { cx: 82,  cy: 240, w: 46, h: 78,  isFront: true,  isLeft: true  },
  fr: { cx: 318, cy: 240, w: 46, h: 78,  isFront: true,  isLeft: false },
  rl: { cx: 76,  cy: 600, w: 54, h: 96,  isFront: false, isLeft: true  },
  rr: { cx: 324, cy: 600, w: 54, h: 96,  isFront: false, isLeft: false },
} as const

type TireKey = keyof typeof TIRES
type TireGeom = (typeof TIRES)[TireKey]

export function CarPanel() {
  const data = useSimulationStore(s => s.data)
  const pos = useUIStore(s => s.pos)
  const hoveredCorner = useUIStore(s => s.hoveredCorner)
  const setHoveredCorner = useUIStore(s => s.setHoveredCorner)

  const lapIdx = data
    ? Math.min(data.laps.length - 1, Math.max(0, Math.floor(pos - 1)))
    : 0
  const lapNumber = lapIdx + 1
  const lap = data?.laps[lapIdx] ?? null
  const compound = data?.meta.stint.compound ?? 'MEDIUM'
  const cColor = compoundColor(compound)

  if (!data) {
    return <PanelSkeleton label="CAR — SELECT STINT AND RUN MODEL" />
  }

  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateRows: '38px 1fr auto', minHeight: 0 }}>
      <PanelHeader
        title="CAR"
        subtitle="SF-24 · TOP-DOWN · INTEGRATED TELEMETRY"
        right={<span>LAP {String(lapNumber).padStart(2, '0')}</span>}
      />

      {/* SVG canvas */}
      <div style={{
        position: 'relative',
        overflow: 'hidden',
        minHeight: 0,
        background: 'radial-gradient(ellipse at center, #0a1018 0%, var(--panel-bg) 70%)',
      }}>
        <svg
          viewBox={`0 0 ${CAR_W} ${CAR_H}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ width: '100%', height: '100%', display: 'block' }}
        >
          <defs>
            <pattern id="tech-grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="var(--rule)" strokeWidth="0.3" opacity="0.6" />
            </pattern>
            <radialGradient id="brake-glow">
              <stop offset="0%" stopColor="#FFB020" stopOpacity="0.9" />
              <stop offset="60%" stopColor="#FF6A00" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#FF3300" stopOpacity="0" />
            </radialGradient>
          </defs>

          <rect width={CAR_W} height={CAR_H} fill="url(#tech-grid)" />

          {/* Centerline */}
          <line x1={CAR_W / 2} y1="10" x2={CAR_W / 2} y2={CAR_H - 10}
            stroke="var(--rule-strong)" strokeWidth="0.5" strokeDasharray="3 5" opacity="0.5" />

          {/* Axle reference lines */}
          <g opacity="0.35">
            <line x1="30" y1={TIRES.fl.cy} x2={CAR_W - 30} y2={TIRES.fl.cy}
              stroke="var(--rule-strong)" strokeWidth="0.5" strokeDasharray="2 4" />
            <line x1="20" y1={TIRES.rl.cy} x2={CAR_W - 20} y2={TIRES.rl.cy}
              stroke="var(--rule-strong)" strokeWidth="0.5" strokeDasharray="2 4" />
            <text x={CAR_W - 28} y={TIRES.fl.cy - 4} fill="var(--text-muted)"
              fontFamily="var(--mono)" fontSize="7" letterSpacing="1.2" textAnchor="end">FRONT AXLE</text>
            <text x={CAR_W - 28} y={TIRES.rl.cy - 4} fill="var(--text-muted)"
              fontFamily="var(--mono)" fontSize="7" letterSpacing="1.2" textAnchor="end">REAR AXLE</text>
          </g>

          <CarChassis />

          {/* Tires */}
          {(Object.entries(TIRES) as [TireKey, TireGeom][]).map(([c, geom]) => (
            <CarWheel
              key={c}
              corner={c as Corner}
              geom={geom}
              lap={lap}
              hovered={hoveredCorner === c}
              onHover={setHoveredCorner}
            />
          ))}

          {/* Compound strip at top */}
          <g transform="translate(140, 18)">
            <rect width="120" height="3" fill={cColor} />
            <text x="60" y="15" fill="var(--text-dim)" fontFamily="var(--mono)"
              fontSize="8" textAnchor="middle" letterSpacing="2">
              {compound} · AGE {lapNumber}
            </text>
          </g>

          {/* Dimension annotations */}
          <g fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="7" letterSpacing="1">
            {/* Wheelbase */}
            <line x1="360" y1={TIRES.fl.cy} x2="360" y2={TIRES.rl.cy}
              stroke="var(--text-muted)" strokeWidth="0.5" />
            <line x1="356" y1={TIRES.fl.cy} x2="364" y2={TIRES.fl.cy}
              stroke="var(--text-muted)" strokeWidth="0.5" />
            <line x1="356" y1={TIRES.rl.cy} x2="364" y2={TIRES.rl.cy}
              stroke="var(--text-muted)" strokeWidth="0.5" />
            <text x="368" y={(TIRES.fl.cy + TIRES.rl.cy) / 2 + 2}>WB 3600</text>
            {/* Front track */}
            <line x1={TIRES.fl.cx} y1="200" x2={TIRES.fr.cx} y2="200"
              stroke="var(--text-muted)" strokeWidth="0.5" />
            <text x={CAR_W / 2} y="196" textAnchor="middle">TRACK 2000</text>
          </g>
        </svg>
      </div>

      <CarFooter lap={lap} />
    </div>
  )
}
