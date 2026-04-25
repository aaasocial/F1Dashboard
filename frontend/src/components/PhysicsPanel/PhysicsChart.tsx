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
  const xZoom = useUIStore(s => s.xZoom)
  const hovered = hoveredCorner === corner

  // Chart padding constants — defined here so they're available to effects and render
  const PAD_L = 40, PAD_R = 12
  const chartIw = Math.max(10, size.w - PAD_L - PAD_R)

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

  // Wheel zoom + drag pan against shared xZoom (D-22)
  useEffect(() => {
    const el = ref.current
    if (!el) return

    function clamp(d0: number, d1: number, lo: number, hi: number, minRange: number): [number, number] {
      let a = Math.max(lo, d0)
      let b = Math.min(hi, d1)
      if (b - a < minRange) {
        // Re-center
        const c = (a + b) / 2
        a = Math.max(lo, c - minRange / 2)
        b = Math.min(hi, a + minRange)
      }
      return [a, b]
    }

    function onWheel(e: WheelEvent) {
      e.preventDefault()
      const cur = useUIStore.getState().xZoom ?? [1, maxLap]
      const [d0, d1] = cur
      const range = d1 - d0
      const factor = e.deltaY > 0 ? 1.15 : 0.87
      const newRange = Math.max(1, Math.min(maxLap - 1, range * factor))
      // Center the new range on the cursor lap
      const rect = el!.getBoundingClientRect()
      const cursorPx = e.clientX - rect.left
      const cursorFrac = (cursorPx - PAD_L) / chartIw
      const cursorLap = d0 + cursorFrac * range
      let nd0 = cursorLap - cursorFrac * newRange
      let nd1 = nd0 + newRange
      ;[nd0, nd1] = clamp(nd0, nd1, 1, maxLap, 1)
      const isFullRange = nd0 <= 1 && nd1 >= maxLap
      useUIStore.getState().setXZoom(isFullRange ? null : [nd0, nd1])
    }

    let dragStart: { x: number; domain: [number, number] } | null = null
    function onPointerDown(e: PointerEvent) {
      // Only main button; ignore right-click (handled by ChartContextMenu)
      if (e.button !== 0) return
      dragStart = {
        x: e.clientX,
        domain: useUIStore.getState().xZoom ?? [1, maxLap],
      }
      ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
    }
    function onPointerMove(e: PointerEvent) {
      if (!dragStart) return
      const dx = e.clientX - dragStart.x
      const [d0, d1] = dragStart.domain
      const lapPerPx = (d1 - d0) / chartIw
      const shift = -dx * lapPerPx
      let nd0 = d0 + shift
      let nd1 = nd0 + (d1 - d0)
      if (nd0 < 1) { nd0 = 1; nd1 = nd0 + (d1 - d0) }
      if (nd1 > maxLap) { nd1 = maxLap; nd0 = nd1 - (d1 - d0) }
      const isFullRange = nd0 <= 1 && nd1 >= maxLap
      useUIStore.getState().setXZoom(isFullRange ? null : [nd0, nd1])
    }
    function onPointerUp() { dragStart = null }

    // Pitfall 7: wheel listener must be passive: false to allow preventDefault
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('pointerdown', onPointerDown)
    el.addEventListener('pointermove', onPointerMove)
    el.addEventListener('pointerup', onPointerUp)
    el.addEventListener('pointercancel', onPointerUp)
    return () => {
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('pointerdown', onPointerDown)
      el.removeEventListener('pointermove', onPointerMove)
      el.removeEventListener('pointerup', onPointerUp)
      el.removeEventListener('pointercancel', onPointerUp)
    }
  }, [maxLap, chartIw])

  // Guard empty data (Pitfall 4)
  if (revealedLaps.length === 0) return null

  const { w, h } = size
  const padL = PAD_L, padT = 8, padB = isLast ? 18 : 6
  const iw = chartIw
  const ih = Math.max(10, h - padT - padB)
  const [yMin, yMax] = cfg.domain

  const [domainStart, domainEnd] = xZoom ?? [1, maxLap]
  const sx = scaleLinear().domain([domainStart, domainEnd]).range([padL, padL + iw])
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
