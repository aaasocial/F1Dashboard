import { useRef, useState, useEffect, useCallback } from 'react'
import { useUIStore } from '../../stores/useUIStore'
import { useSimulationStore } from '../../stores/useSimulationStore'
import type { LapData } from '../../lib/types'

interface ScrubberProps {
  maxLap: number
}

// D-04: sector colors from CONTEXT.md
const SECTOR_COLORS = ['#3a98b4', '#2a7a93', '#1d6278'] as const

function derivePitLaps(laps: LapData[] | undefined): number[] {
  if (!laps) return []
  // Pit stops: laps after lap 1 where stint_age === 0 (start of subsequent stint)
  return laps.filter(l => l.lap_number > 1 && l.stint_age === 0).map(l => l.lap_number)
}

export function Scrubber({ maxLap }: ScrubberProps) {
  const pos = useUIStore(s => s.pos)
  const seek = useUIStore(s => s.seek)
  const laps = useSimulationStore(s => s.data?.laps)
  const ref = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState(false)

  const frac = (pos - 1) / Math.max(1, maxLap - 1)

  const onPointer = useCallback((e: PointerEvent | React.PointerEvent) => {
    if (!ref.current) return
    const r = ref.current.getBoundingClientRect()
    const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width))
    seek(1 + x * (maxLap - 1))
  }, [seek, maxLap])

  useEffect(() => {
    if (!dragging) return
    const mv = (e: PointerEvent) => onPointer(e)
    const up = () => setDragging(false)
    window.addEventListener('pointermove', mv)
    window.addEventListener('pointerup', up)
    return () => {
      window.removeEventListener('pointermove', mv)
      window.removeEventListener('pointerup', up)
    }
  }, [dragging, onPointer])

  // D-04 sector segments — three equal thirds across maxLap
  const sectorRanges = [
    { start: 1, end: 1 + (maxLap - 1) / 3 },
    { start: 1 + (maxLap - 1) / 3, end: 1 + 2 * (maxLap - 1) / 3 },
    { start: 1 + 2 * (maxLap - 1) / 3, end: maxLap },
  ]

  // D-04 pit markers — laps after lap 1 with stint_age === 0
  const pitLaps = derivePitLaps(laps)

  return (
    <div
      ref={ref}
      onPointerDown={e => { setDragging(true); onPointer(e); (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId) }}
      style={{ height: 24, position: 'relative', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
      data-testid="scrubber"
    >
      {/* Track rail (base) */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 10, height: 3, background: 'var(--rule-strong)' }} />

      {/* Sector segments — D-04 */}
      {sectorRanges.map((s, i) => {
        const left = ((s.start - 1) / Math.max(1, maxLap - 1)) * 100
        const width = ((s.end - s.start) / Math.max(1, maxLap - 1)) * 100
        return (
          <div
            key={`sec-${i}`}
            data-testid={`sector-segment-${i}`}
            style={{
              position: 'absolute',
              left: `${left}%`,
              width: `${width}%`,
              top: 10,
              height: 3,
              background: SECTOR_COLORS[i],
              opacity: 0.65,
            }}
          />
        )
      })}

      {/* Progress fill (overlays sector tint) */}
      <div style={{
        position: 'absolute', left: 0, top: 10, height: 3,
        width: `${frac * 100}%`,
        background: 'var(--accent)', opacity: 0.85,
      }} />

      {/* Per-lap tick marks */}
      {Array.from({ length: maxLap }).map((_, i) => (
        <div key={`tick-${i}`} style={{
          position: 'absolute',
          left: `${(i / Math.max(1, maxLap - 1)) * 100}%`,
          top: 7, width: 1, height: 9,
          background: 'var(--rule-strong)',
          transform: 'translateX(-0.5px)',
        }} />
      ))}

      {/* Pit-stop markers — D-04 */}
      {pitLaps.map(lapNum => {
        const left = ((lapNum - 1) / Math.max(1, maxLap - 1)) * 100
        return (
          <div
            key={`pit-${lapNum}`}
            data-testid="pit-marker"
            title={`Pit stop — lap ${lapNum}`}
            style={{
              position: 'absolute',
              left: `${left}%`,
              top: 4,
              width: 2,
              height: 16,
              background: '#ffffff',
              transform: 'translateX(-1px)',
              pointerEvents: 'none',
            }}
          />
        )
      })}

      {/* Handle */}
      <div style={{
        position: 'absolute',
        left: `${frac * 100}%`,
        top: 4, width: 3, height: 16,
        background: 'var(--accent)',
        transform: 'translateX(-50%)',
        boxShadow: '0 0 8px rgba(0,229,255,0.7)',
      }} />
    </div>
  )
}
