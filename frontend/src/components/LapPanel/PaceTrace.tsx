import { useRef, useState, useEffect } from 'react'
import { scaleLinear } from 'd3-scale'
import { line, area } from 'd3-shape'
import { extent } from 'd3-array'
import { useUIStore } from '../../stores/useUIStore'
import { fmtLapTime } from '../../lib/formatters'
import type { LapData } from '../../lib/types'

interface PaceTraceProps {
  revealedLaps: LapData[]
  currentLapIdx: number
  maxLap: number
}

export function PaceTrace({ revealedLaps, currentLapIdx, maxLap }: PaceTraceProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 420, h: 120 })
  const hoveredLap = useUIStore(s => s.hoveredLap)
  const setHoveredLap = useUIStore(s => s.setHoveredLap)

  // ResizeObserver — wrap setState in requestAnimationFrame to prevent loop errors (Pitfall 3)
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

  const { w, h } = size
  const padL = 34, padR = 10, padT = 20, padB = 20
  const iw = Math.max(1, w - padL - padR)
  const ih = Math.max(1, h - padT - padB)

  // Guard empty data (Pitfall 4)
  if (revealedLaps.length < 2) {
    return <div ref={ref} style={{ flex: 1, minHeight: 0 }} />
  }

  const data = revealedLaps.map(l => ({ lap: l.lap_number, time: l.lap_time.mean }))
  const [timeMin, timeMax] = extent(data, d => d.time) as [number, number]
  const sx = scaleLinear().domain([1, maxLap]).range([padL, padL + iw])
  const sy = scaleLinear().domain([timeMin - 0.1, timeMax + 0.1]).range([padT + ih, padT])

  const linePath = line<typeof data[0]>().x(d => sx(d.lap)).y(d => sy(d.time))
  const areaPath = area<typeof data[0]>().x(d => sx(d.lap)).y0(padT + ih).y1(d => sy(d.time))

  const bestLap = data.reduce((b, d) => d.time < b.time ? d : b, data[0])
  const crosshairX = hoveredLap != null ? sx(hoveredLap) : sx(currentLapIdx + 1)

  function onMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - rect.left
    const rawLap = Math.round((px - padL) / iw * (maxLap - 1) + 1)
    const clampedLap = Math.max(1, Math.min(revealedLaps.length, rawLap))
    setHoveredLap(clampedLap)
  }

  // Y grid lines at 0.25/0.5/0.75 of domain
  const yTicks = [0.25, 0.5, 0.75].map(f => timeMin - 0.1 + f * (timeMax - timeMin + 0.2))

  return (
    <div ref={ref} style={{ flex: 1, minHeight: 0, position: 'relative' }}>
      <svg
        width={w} height={h}
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHoveredLap(null)}
        style={{ display: 'block' }}
      >
        {/* Y grid */}
        {yTicks.map((t, i) => (
          <line key={i} x1={padL} x2={padL + iw} y1={sy(t)} y2={sy(t)}
            stroke="var(--rule)" strokeWidth="0.5" opacity="0.7" />
        ))}

        {/* Area fill */}
        <path d={areaPath(data) ?? ''} fill="var(--accent)" opacity="0.1" />

        {/* Line */}
        <path d={linePath(data) ?? ''} fill="none" stroke="var(--accent)"
          strokeWidth="1.6" strokeLinejoin="round" />

        {/* Lap dots */}
        {data.map(d => (
          <circle key={d.lap}
            cx={sx(d.lap)} cy={sy(d.time)}
            r={d.lap === bestLap.lap ? 3 : 1.6}
            fill={d.lap === bestLap.lap ? 'var(--purple)' : 'var(--accent)'}
            stroke={d.lap === bestLap.lap ? 'var(--panel-bg)' : 'none'}
            strokeWidth={d.lap === bestLap.lap ? 1.5 : 0}
          />
        ))}

        {/* Vertical crosshair */}
        <line x1={crosshairX} x2={crosshairX} y1={padT} y2={padT + ih}
          stroke="var(--accent)" strokeWidth="0.8" strokeDasharray="3 3" opacity="0.7" />

        {/* Y axis labels */}
        <text x={padL - 2} y={padT} fill="var(--text-muted)" fontSize="7"
          fontFamily="var(--mono)" textAnchor="end">
          {fmtLapTime(timeMin - 0.1)}
        </text>
        <text x={padL - 2} y={padT + ih} fill="var(--text-muted)" fontSize="7"
          fontFamily="var(--mono)" textAnchor="end">
          {fmtLapTime(timeMax + 0.1)}
        </text>

        {/* X axis labels every 5 laps */}
        {[1, ...Array.from({ length: Math.floor(maxLap / 5) }, (_, i) => (i + 1) * 5), maxLap].map(l => (
          <text key={l} x={sx(l)} y={padT + ih + 14}
            fill="var(--text-muted)" fontSize="7" fontFamily="var(--mono)" textAnchor="middle">
            {l}
          </text>
        ))}
      </svg>
    </div>
  )
}
