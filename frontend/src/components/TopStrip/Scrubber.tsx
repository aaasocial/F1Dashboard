import { useRef, useState, useEffect, useCallback } from 'react'
import { useUIStore } from '../../stores/useUIStore'

interface ScrubberProps {
  maxLap: number
}

export function Scrubber({ maxLap }: ScrubberProps) {
  const pos = useUIStore(s => s.pos)
  const seek = useUIStore(s => s.seek)
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

  return (
    <div
      ref={ref}
      onPointerDown={e => { setDragging(true); onPointer(e) }}
      style={{ height: 24, position: 'relative', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
    >
      {/* Track rail */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 10, height: 3, background: 'var(--rule-strong)' }} />
      {/* Progress fill */}
      <div style={{ position: 'absolute', left: 0, top: 10, height: 3, width: `${frac * 100}%`, background: 'var(--accent)' }} />
      {/* Per-lap tick marks */}
      {Array.from({ length: maxLap }).map((_, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: `${(i / Math.max(1, maxLap - 1)) * 100}%`,
          top: 7, width: 1, height: 9,
          background: 'var(--rule-strong)',
          transform: 'translateX(-0.5px)',
        }} />
      ))}
      {/* Handle — 3×16px accent bar with glow */}
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
