import { useEffect } from 'react'
import { TopStrip } from './components/TopStrip/TopStrip'
import { CarPanel } from './components/CarPanel/CarPanel'
import { LapPanel } from './components/LapPanel/LapPanel'
import { MapPanel } from './components/MapPanel/MapPanel'
import { PhysicsPanel } from './components/PhysicsPanel/PhysicsPanel'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { useUIStore } from './stores/useUIStore'
import { useSimulationStore } from './stores/useSimulationStore'
import { useHashSync } from './lib/useHashSync'
import { useShallow } from 'zustand/react/shallow'

const LAP_SECONDS = 4.0  // 1 lap = 4 real seconds at 1× (from design reference)

export function App() {
  // Wire URL hash ↔ store sync (DASH-01)
  useHashSync()

  const { playing, speed, mode, seek, setPlaying } = useUIStore(
    useShallow(s => ({
      playing: s.playing,
      speed: s.speed,
      mode: s.mode,
      seek: s.seek,
      setPlaying: s.setPlaying,
    }))
  )
  // Use mapped SimulationResult.laps (not raw per_lap) — correct field per Plan 02 types
  const maxLap = useSimulationStore(s => s.data?.laps.length ?? 22)

  // Animation tick — mirrors cockpit-app.jsx useEffect tick loop
  useEffect(() => {
    if (!playing) return
    let rafId: number
    let last = performance.now()
    const step = (t: number) => {
      const dt = (t - last) / 1000
      last = t
      const current = useUIStore.getState().pos
      const next = current + (dt * speed) / LAP_SECONDS
      if (next >= maxLap + 0.999) {
        if (mode === 'replay') {
          seek(1.0)
        } else {
          setPlaying(false)
          seek(maxLap + 0.999)
        }
      } else {
        seek(next)
      }
      rafId = requestAnimationFrame(step)
    }
    rafId = requestAnimationFrame(step)
    return () => cancelAnimationFrame(rafId)
  }, [playing, speed, mode, maxLap, seek, setPlaying])

  return (
    <div style={{
      minHeight: '100vh',
      display: 'grid',
      gridTemplateRows: '52px 1fr',
      background: 'var(--bg)',
    }}>
      <TopStrip />

      {/* 5-panel cockpit grid — exact values from cockpit-app.jsx */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(460px, 33%) minmax(420px, 32%) minmax(480px, 35%)',
          gridTemplateRows: 'minmax(400px, 55%) minmax(320px, 45%)',
          gap: 1,
          background: 'var(--rule)',
          padding: 1,
          minHeight: 0,
        }}
      >
        {/* Left column: CarPanel spans both rows */}
        <div style={{ gridColumn: 1, gridRow: '1 / span 2', background: 'var(--panel-bg)', minHeight: 0 }}>
          <ErrorBoundary label="CarPanel">
            <CarPanel />
          </ErrorBoundary>
        </div>

        {/* Middle column: LapPanel spans both rows */}
        <div style={{ gridColumn: 2, gridRow: '1 / span 2', background: 'var(--panel-bg)', minHeight: 0 }}>
          <ErrorBoundary label="LapPanel">
            <LapPanel />
          </ErrorBoundary>
        </div>

        {/* Right top: MapPanel */}
        <div style={{ gridColumn: 3, gridRow: 1, background: 'var(--panel-bg)', minHeight: 0 }}>
          <ErrorBoundary label="MapPanel">
            <MapPanel />
          </ErrorBoundary>
        </div>

        {/* Right bottom: PhysicsPanel */}
        <div style={{ gridColumn: 3, gridRow: 2, background: 'var(--panel-bg)', minHeight: 0 }}>
          <ErrorBoundary label="PhysicsPanel">
            <PhysicsPanel />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}
