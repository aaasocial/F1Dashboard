import { useRef, useState, useEffect } from 'react'
import { scaleLinear } from 'd3-scale'
import { line, area } from 'd3-shape'
import { useUIStore } from '../../stores/useUIStore'
import { useShallow } from 'zustand/react/shallow'
import { CORNER_COLORS } from '../../lib/scales'
import type { LapData, Corner } from '../../lib/types'

type MetricKey = 't_tread' | 'grip' | 'e_tire' | 'slip_angle'

interface MetricConfig {
  label: string
  unit: string
  fmt: (v: number) => string
  domain: [number, number]
  accent: string
}

interface PhysicsChartProps {
  corner: Corner
  metricKey: MetricKey
  cfg: MetricConfig
  revealedLaps: LapData[]
  isLast: boolean
  maxLap: number
}

export function PhysicsChart({ corner, metricKey, cfg, revealedLaps, isLast, maxLap }: PhysicsChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 480, h: 70 })
  const [hoverLap, setHoverLap] = useState<number | null>(null)

  const { hoveredCorner, setHoveredCorner, setHoveredLap } = useUIStore(
    useShallow(s => ({ hoveredCorner: s.hoveredCorner, setHoveredCorner: s.setHoveredCorner, setHoveredLap: s.setHoveredLap }))
  )
  const hovered = hoveredCorner === corner

  // ResizeObserver with rAF guard (Pitfall 3)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(entries => {
      requestAnimationFrame(() => {
        for (const e of entries) {
          setSize({ w: e.contentRect.width, h: e.contentRect.height })
        }
      })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Guard empty data (Pitfall 4)
  if (revealedLaps.length === 0) return null

  const { w, h } = size
  const padL = 40, padR = 12, padT = 8, padB = isLast ? 18 : 6
  const iw = Math.max(10, w - padL - padR)
  const ih = Math.max(10, h - padT - padB)
  const [yMin, yMax] = cfg.domain

  const sx = scaleLinear().domain([1, maxLap]).range([padL, padL + iw])
  const sy = scaleLinear().domain([yMin, yMax]).range([padT + ih, padT])

  // Field key for this metric + corner combo
  const fieldKey = `${metricKey}_${corner}` as keyof LapData

  const data = revealedLaps.map(l => {
    const ci = l[fieldKey] as { mean: number; lo_95: number; hi_95: number }
    return { lap: l.lap_number, mean: ci.mean, lo: ci.lo_95, hi: ci.hi_95 }
  })

  // D3 CI band (area) and mean line
  const ciArea = area<typeof data[0]>()
    .x(d => sx(d.lap))
    .y0(d => sy(d.lo))
    .y1(d => sy(d.hi))

  const meanLine = line<typeof data[0]>()
    .x(d => sx(d.lap))
    .y(d => sy(d.mean))

  const ciPath = ciArea(data) ?? ''
  const meanPath = meanLine(data) ?? ''

  const color = CORNER_COLORS[corner]

  // Y axis: 3 ticks at min, mid, max of domain
  const yTicks = [yMin, (yMin + yMax) / 2, yMax]

  // Horizontal grid lines at 0, 1/3, 2/3, 1 of domain
  const gridFracs = [0, 1/3, 2/3, 1]

  // Hover: compute hovered lap from mouse X
  function onMouseMove(e: React.MouseEvent) {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const px = e.clientX - rect.left
    const rawLap = Math.round((px - padL) / iw * (maxLap - 1) + 1)
    const clampedLap = Math.max(1, Math.min(data.length > 0 ? data[data.length-1].lap : 1, rawLap))
    setHoverLap(clampedLap)
    setHoveredLap(clampedLap)   // linked hover across all zones (VIZ-05)
  }
  function onMouseLeave() {
    setHoverLap(null)
    setHoveredLap(null)
    setHoveredCorner(null)
  }
  function onMouseEnter() {
    setHoveredCorner(corner)    // linked hover → CarPanel footer highlight (VIZ-05)
  }

  // Tooltip position + data
  const tooltipDatum = hoverLap != null ? data.find(d => d.lap === hoverLap) : null
  const tooltipX = hoverLap != null ? sx(hoverLap) : null

  return (
    <div
      ref={ref}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      onMouseEnter={onMouseEnter}
      style={{
        position: 'relative',
        background: hovered ? 'var(--panel-header-hi)' : 'transparent',
        borderLeft: hovered ? `2px solid ${color}` : '2px solid transparent',
        minHeight: 0,
      }}
    >
      <svg width={w} height={h} style={{ display: 'block' }}>
        {/* Horizontal grid lines */}
        {gridFracs.map((f, i) => {
          const yVal = yMin + f * (yMax - yMin)
          return (
            <line key={i}
              x1={padL} x2={padL + iw}
              y1={sy(yVal)} y2={sy(yVal)}
              stroke="var(--rule)" strokeWidth="0.4" opacity="0.7"
            />
          )
        })}

        {/* Vertical grid every 5 laps */}
        {Array.from({ length: Math.floor(maxLap / 5) + 1 }, (_, i) => i * 5 + 1)
          .filter(l => l <= maxLap)
          .map(l => (
            <line key={l}
              x1={sx(l)} x2={sx(l)}
              y1={padT} y2={padT + ih}
              stroke="var(--rule)" strokeWidth="0.4" opacity="0.5"
            />
          ))}

        {/* CI band — area polygon hi→lo — VISUALLY DISTINCT from mean line (VIZ-04) */}
        {ciPath && (
          <path d={ciPath} fill={color} opacity={0.12} />
        )}

        {/* Mean line — solid, full opacity, visually distinct from faint CI band */}
        {meanPath && (
          <path d={meanPath} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
        )}

        {/* Dots at each lap */}
        {data.map(d => (
          <circle key={d.lap}
            cx={sx(d.lap)} cy={sy(d.mean)}
            r={1.6} fill={color}
          />
        ))}

        {/* Hover crosshair */}
        {hoverLap != null && tooltipX != null && (
          <line
            x1={tooltipX} x2={tooltipX}
            y1={padT} y2={padT + ih}
            stroke={color} strokeWidth={1} opacity={0.7}
          />
        )}
        {hoverLap != null && tooltipDatum && tooltipX != null && (
          <circle
            cx={tooltipX} cy={sy(tooltipDatum.mean)}
            r={3} fill={color}
          />
        )}

        {/* Y axis ticks (3: min, mid, max) */}
        {yTicks.map((v, i) => (
          <text key={i}
            x={padL - 4} y={sy(v) + 3}
            fill="var(--text-muted)" fontSize="7" fontFamily="var(--mono)"
            textAnchor="end">
            {cfg.fmt(v)}
          </text>
        ))}

        {/* X axis labels on last chart only */}
        {isLast && [1, ...Array.from({ length: Math.floor(maxLap/5) }, (_, i) => (i+1)*5), maxLap]
          .filter((l, i, arr) => arr.indexOf(l) === i && l <= maxLap)
          .map(l => (
            <text key={l}
              x={sx(l)} y={padT + ih + 14}
              fill="var(--text-muted)" fontSize="7" fontFamily="var(--mono)" textAnchor="middle">
              L{l}
            </text>
          ))}

        {/* Corner label badge top-left */}
        <rect x={padL + 2} y={padT + 1} width={24} height={12}
          fill="rgba(0,0,0,0.6)" stroke={color} strokeWidth={0.6} />
        <text x={padL + 14} y={padT + 10}
          fill={color} fontSize={9} fontFamily="var(--mono)" fontWeight={700}
          letterSpacing={1} textAnchor="middle">
          {corner.toUpperCase()}
        </text>
      </svg>

      {/* Floating tooltip card */}
      {hoverLap != null && tooltipDatum != null && tooltipX != null && (
        <div style={{
          position: 'absolute',
          left: Math.min(tooltipX + 8, w - 90),
          top: padT,
          background: 'rgba(0,0,0,0.85)',
          border: `1px solid ${color}`,
          padding: '4px 8px',
          fontFamily: 'var(--mono)',
          fontSize: 8.5,
          color: 'var(--text)',
          pointerEvents: 'none',
          whiteSpace: 'nowrap',
        }}>
          L{hoverLap}&nbsp;&nbsp;{cfg.fmt(tooltipDatum.mean)}&nbsp;&nbsp;±{((tooltipDatum.hi - tooltipDatum.lo) / 2).toFixed(1)}
        </div>
      )}
    </div>
  )
}
