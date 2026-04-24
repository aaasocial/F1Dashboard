// CarWheel — rectangular top-down tire schematic per locked design reference.
// NOT a circular arc/ring gauge. The viridis-filled rectangle IS the temperature
// visualization (gauge), mapping 60–120°C to the viridis color range.
// Ported from design_handoff_f1_cockpit/design/cockpit-car.jsx CarWheel()

import { tempToViridis, CORNER_COLORS, CORNER_LABELS } from '../../lib/scales'
import type { LapData, Corner } from '../../lib/types'

interface WheelGeom {
  cx: number
  cy: number
  w: number
  h: number
  isFront: boolean
  isLeft: boolean
}

interface CarWheelProps {
  corner: Corner
  geom: WheelGeom
  lap: LapData | null
  hovered: boolean
  onHover: (corner: Corner | null) => void
}

export function CarWheel({ corner, geom, lap, hovered, onHover }: CarWheelProps) {
  const { cx, cy, w, h, isFront, isLeft } = geom

  // --- Derived values (with safe defaults for null lap) ---
  const tempMean = lap?.[`t_tread_${corner}` as keyof LapData] != null
    ? (lap[`t_tread_${corner}` as keyof LapData] as { mean: number }).mean
    : 90
  const tempHi = lap?.[`t_tread_${corner}` as keyof LapData] != null
    ? (lap[`t_tread_${corner}` as keyof LapData] as { hi_95: number }).hi_95
    : 95
  const tempLo = lap?.[`t_tread_${corner}` as keyof LapData] != null
    ? (lap[`t_tread_${corner}` as keyof LapData] as { lo_95: number }).lo_95
    : 85

  const gripMean = lap?.[`grip_${corner}` as keyof LapData] != null
    ? (lap[`grip_${corner}` as keyof LapData] as { mean: number }).mean
    : 1.35

  const eTireMean = lap?.[`e_tire_${corner}` as keyof LapData] != null
    ? (lap[`e_tire_${corner}` as keyof LapData] as { mean: number }).mean
    : 5

  const slipMean = lap?.[`slip_angle_${corner}` as keyof LapData] != null
    ? (lap[`slip_angle_${corner}` as keyof LapData] as { mean: number }).mean
    : 3.0

  // Temperature → viridis fill (THIS is the temperature visualization per design lock)
  const tempColor = tempToViridis(tempMean)

  // Wear percentage and band erosion count
  const wearPct = Math.max(0, Math.min(1, eTireMean / 22))
  const wearBands = Math.round(wearPct * 8)

  // Grip normalization and lit segments
  const gripNorm = Math.max(0, Math.min(1, (gripMean - 1.05) / 0.45))
  const litSegments = Math.round(gripNorm * 10)

  // Brake temperature and glow opacity
  const brakeT = (isFront ? 560 : 410) + eTireMean * 22 + slipMean * 28
  const brakeNorm = Math.max(0, Math.min(1, (brakeT - 300) / 500))

  // CI halo stroke width — wider = more uncertainty
  const ciStroke = 0.6 + Math.min(3, (tempHi - tempLo) * 0.12)

  // Tire rectangle top-left origin
  const x = cx - w / 2
  const y = cy - h / 2

  // Tread band height
  const bandH = h / 8

  // Slip angle tick rotation
  const slipAngle = Math.max(-6, Math.min(6, slipMean)) * (isLeft ? -1 : 1)

  // Grip ladder x position (outboard)
  const gripX = isLeft ? x - 16 : x + w + 2

  // Wear bar color by threshold
  const wearColor = wearPct > 0.7 ? '#FF3344' : wearPct > 0.45 ? '#FFB020' : '#22E27A'

  return (
    <g
      style={{ cursor: 'pointer' }}
      onMouseEnter={() => onHover(corner)}
      onMouseLeave={() => onHover(null)}
    >
      {/* 1. Brake glow ellipse behind tire */}
      <ellipse cx={cx} cy={cy} rx={w * 0.75} ry={h * 0.55}
        fill="url(#brake-glow)"
        opacity={0.25 + brakeNorm * 0.55} />

      {/* 2. Tire outer rim */}
      <rect x={x - 1.5} y={y - 1.5} width={w + 3} height={h + 3}
        fill="none"
        stroke={hovered ? 'var(--accent)' : 'var(--text-muted)'}
        strokeWidth={hovered ? '1.4' : '0.8'} />

      {/* 3. Tire body — viridis temperature fill (the temperature visualization) */}
      <rect x={x} y={y} width={w} height={h}
        fill={tempColor} opacity="0.88" />

      {/* 4. Tread grooves — 7 lines dividing 8 bands */}
      {Array.from({ length: 7 }).map((_, i) => (
        <line key={i}
          x1={x} y1={y + (i + 1) * bandH}
          x2={x + w} y2={y + (i + 1) * bandH}
          stroke="rgba(0,0,0,0.45)" strokeWidth="0.8" />
      ))}

      {/* 5. Wear erosion — bands removed from leading edge */}
      {Array.from({ length: wearBands }).map((_, i) => {
        // Front: erosion from TOP (leading edge)
        // Rear: erosion from BOTTOM (leading edge)
        const bandY = isFront
          ? y + i * bandH
          : y + h - (i + 1) * bandH
        return (
          <rect key={i}
            x={x} y={bandY}
            width={w} height={bandH * 0.85}
            fill="rgba(10,14,21,0.78)" />
        )
      })}

      {/* 6. Temp number badge centered on tire */}
      <rect x={cx - 16} y={cy - 9} width="32" height="18"
        fill="rgba(0,0,0,0.58)" />
      <text x={cx} y={cy + 4} fill="#fff" fontFamily="var(--mono)"
        fontSize={isFront ? '11' : '12'} fontWeight="700" textAnchor="middle"
        letterSpacing="0.5">
        {tempMean.toFixed(0)}°
      </text>

      {/* 7. Corner label — inboard side */}
      <text
        x={isLeft ? x + w + 6 : x - 6}
        y={y + 10}
        fill={hovered ? 'var(--accent)' : CORNER_COLORS[corner]}
        fontFamily="var(--mono)" fontSize="11" fontWeight="700" letterSpacing="2"
        textAnchor={isLeft ? 'start' : 'end'}>
        {CORNER_LABELS[corner]}
      </text>

      {/* 8. Grip ladder — outboard, 10 vertical segments */}
      <g transform={`translate(${gripX}, ${y})`}>
        {Array.from({ length: 10 }).map((_, i) => {
          const seg = 10 - 1 - i
          const lit = seg < litSegments
          return (
            <rect key={i}
              x={0} y={i * (h / 10) + 1}
              width={14} height={h / 10 - 2}
              fill={lit ? 'var(--accent)' : 'var(--rule-strong)'}
              opacity={lit ? (0.4 + 0.6 * (seg / 10)) : 0.5}
            />
          )
        })}
      </g>
      <text x={gripX + 7} y={y - 3}
        fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="7"
        textAnchor="middle" letterSpacing="1">μ</text>
      <text x={gripX + 7} y={y + h + 11}
        fill="var(--accent)" fontFamily="var(--mono)" fontSize="8" fontWeight="600"
        textAnchor="middle">
        {gripMean.toFixed(2)}
      </text>

      {/* 9. Wear bar — horizontal strip below tire */}
      <g transform={`translate(${x}, ${y + h + 4})`}>
        <rect x={0} y={0} width={w} height={3} fill="var(--rule-strong)" />
        <rect x={0} y={0} width={w * wearPct} height={3} fill={wearColor} />
        <text x={w / 2} y={13} fill="var(--text-muted)" fontFamily="var(--mono)"
          fontSize="7" textAnchor="middle" letterSpacing="1">
          WEAR {(wearPct * 100).toFixed(0)}%
        </text>
      </g>

      {/* 10. Slip angle tick — above tire */}
      <g transform={`translate(${cx}, ${y - 8}) rotate(${slipAngle * 2})`}>
        <line x1="0" y1="0" x2="0" y2="-14"
          stroke={hovered ? 'var(--accent)' : 'var(--text-dim)'} strokeWidth="1.2" />
        <circle cx="0" cy="-14" r="1.5" fill={hovered ? 'var(--accent)' : 'var(--text-dim)'} />
      </g>
      <text x={cx} y={y - 28} fill="var(--text-muted)" fontFamily="var(--mono)"
        fontSize="7" textAnchor="middle" letterSpacing="0.8">
        α {slipMean.toFixed(1)}°
      </text>

      {/* 11. Brake temp readout — inboard side */}
      <g transform={`translate(${isLeft ? x + w + 6 : x - 6}, ${cy + 8})`}>
        <text textAnchor={isLeft ? 'start' : 'end'}
          fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="7" letterSpacing="1">BR</text>
        <text y="10" textAnchor={isLeft ? 'start' : 'end'}
          fill="#FFB020" fontFamily="var(--mono)" fontSize="9" fontWeight="600">
          {brakeT.toFixed(0)}°C
        </text>
      </g>

      {/* 12. CI halo — thin rect outset from tire showing temperature uncertainty */}
      <rect x={x - 2} y={y - 2} width={w + 4} height={h + 4}
        fill="none"
        stroke={tempColor}
        strokeWidth={ciStroke}
        opacity="0.35" />

      {/* 13. Hover box outline */}
      {hovered && (
        <rect x={x - 22} y={y - 34} width={w + 44} height={h + 62}
          fill="none" stroke="var(--accent)" strokeWidth="0.7"
          strokeDasharray="3 3" opacity="0.6" />
      )}
    </g>
  )
}
