import { useSimulationStore } from '../../stores/useSimulationStore'
import { useUIStore } from '../../stores/useUIStore'
import { PanelHeader } from '../shared/PanelHeader'
import { PanelSkeleton } from '../shared/Skeleton'
import { PaceTrace } from './PaceTrace'
import { StatusLog } from './StatusLog'
import { fmtLapTime, fmtDelta } from '../../lib/formatters'

export function LapPanel() {
  const data = useSimulationStore(s => s.data)
  const pos = useUIStore(s => s.pos)

  if (!data) return <PanelSkeleton label="LAP — SELECT STINT AND RUN MODEL" />

  const maxLap = data.laps.length
  const lapIdx = Math.min(maxLap - 1, Math.max(0, Math.floor(pos - 1)))
  const lapFrac = Math.max(0, Math.min(0.9999, pos - Math.floor(pos)))
  const lap = data.laps[lapIdx]
  const lapNumber = lapIdx + 1
  const revealedLaps = data.laps.slice(0, lapNumber)

  // Deltas
  const pbTime = Math.min(...revealedLaps.map(l => l.lap_time.mean))
  const deltaPb = lap.lap_time.mean - pbTime
  const deltaModel = lap.lap_time.mean - lap.lap_time.lo_95  // actual vs optimistic model

  // Sector estimation (thirds of lap time)
  const sectorTime = lap.lap_time.mean / 3
  const activeSector = lapFrac < 0.333 ? 0 : lapFrac < 0.667 ? 1 : 2
  const sectorColors = ['var(--purple)', 'var(--ok)', 'var(--warn)']

  // Pace trace elapsed time
  const elapsed = lap.lap_time.mean * lapFrac

  // Stint projection stats
  const currentWear = (['fl', 'fr', 'rl', 'rr'] as const)
    .reduce((sum, c) => sum + (lap[`e_tire_${c}` as keyof typeof lap] as { mean: number }).mean, 0) / 4
  const avgWearPct = (currentWear / 22 * 100).toFixed(0)
  const lastGrip = Math.min(...(['fl', 'fr', 'rl', 'rr'] as const)
    .map(c => (lap[`grip_${c}` as keyof typeof lap] as { mean: number }).mean))
  const gripDecayPerLap = lapNumber > 1
    ? (data.laps[0].grip_fl.mean - lastGrip) / lapNumber
    : 0.01
  const cliffIn = gripDecayPerLap > 0
    ? Math.floor((lastGrip - 1.2) / gripDecayPerLap)
    : 99
  const cliffColor = cliffIn > 6 ? 'var(--ok)' : cliffIn > 3 ? 'var(--warn)' : 'var(--hot)'

  const deltaPbColor = deltaPb <= 0 ? 'var(--ok)' : deltaPb > 0.1 ? 'var(--warn)' : 'var(--text-dim)'
  const deltaModelColor = deltaModel < -0.05 ? 'var(--ok)' : deltaModel > 0.1 ? 'var(--hot)' : 'var(--text-dim)'

  return (
    <div style={{
      height: '100%',
      display: 'grid',
      gridTemplateRows: '38px auto auto 1fr auto auto',
      minHeight: 0,
      background: 'var(--panel-bg)',
    }}>
      <PanelHeader
        title="LAP"
        subtitle="TIMING · DELTA · SECTORS · STINT MODEL"
        right={<span style={{ color: 'var(--text-muted)', fontSize: 9, fontFamily: 'var(--mono)', letterSpacing: 1 }}>
          {data.meta.driver.code ? data.meta.driver.code : 'REPLAY'}
        </span>}
      />

      {/* BIG LAP TIME */}
      <div style={{
        padding: '16px 18px',
        borderBottom: '1px solid var(--rule)',
      }}>
        <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: 2, marginBottom: 4, fontFamily: 'var(--mono)' }}>
          LAP {String(lapNumber).padStart(2, '0')} · IN PROGRESS
        </div>
        <div style={{
          fontSize: 56, fontWeight: 300, color: 'var(--text)', letterSpacing: 1,
          fontFamily: 'var(--mono)',
          textShadow: '0 0 24px rgba(0,229,255,0.25)',
          lineHeight: 1,
          marginBottom: 8,
        }}>
          {fmtLapTime(elapsed)}
          <span style={{ fontSize: 14, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>
            / {fmtLapTime(lap.lap_time.mean)} FINAL
          </span>
        </div>

        {/* Delta blocks */}
        <div style={{ display: 'flex', gap: 12 }}>
          {[
            { label: 'Δ PB', value: deltaPb, color: deltaPbColor },
            { label: 'Δ MODEL', value: deltaModel, color: deltaModelColor },
          ].map(({ label, value, color }) => (
            <div key={label} style={{
              border: '1px solid var(--rule)',
              borderLeft: `2px solid ${color}`,
              padding: '6px 12px',
              minWidth: 80,
            }}>
              <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: 2, marginBottom: 3, fontFamily: 'var(--mono)' }}>
                {label}
              </div>
              <div style={{ fontSize: 20, fontWeight: 500, color, letterSpacing: 0.5, fontFamily: 'var(--mono)' }}>
                {fmtDelta(value)}
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 3 }}>s</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* SECTOR CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 2, padding: '8px 14px' }}>
        {[0, 1, 2].map(si => {
          const active = si === activeSector
          return (
            <div key={si} style={{
              background: 'var(--panel)',
              borderLeft: `3px solid ${sectorColors[si]}`,
              borderTop: active ? '2px solid var(--accent)' : '2px solid transparent',
              boxShadow: active ? '0 0 4px rgba(0,229,255,0.5)' : 'none',
              padding: '6px 8px',
              opacity: active ? 1 : 0.75,
            }}>
              <div style={{ fontSize: 8.5, color: 'var(--text-muted)', letterSpacing: 2, marginBottom: 3, fontFamily: 'var(--mono)' }}>
                S{si + 1} · {active ? 'LIVE' : 'DONE'}
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)', fontFamily: 'var(--mono)' }}>
                {sectorTime.toFixed(3)}s
              </div>
              <div style={{ fontSize: 8.5, color: sectorColors[si], marginTop: 2, fontFamily: 'var(--mono)' }}>
                {si === 0 ? 'SECTOR 1' : si === 1 ? 'SECTOR 2' : 'SECTOR 3'}
              </div>
            </div>
          )
        })}
      </div>

      {/* PACE TRACE */}
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, padding: '0 14px 4px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--text-muted)', marginBottom: 2, fontFamily: 'var(--mono)', letterSpacing: 1 }}>
          <span>PACE · STINT</span>
          <span>{fmtDelta(deltaPb)}</span>
        </div>
        <PaceTrace revealedLaps={revealedLaps} currentLapIdx={lapIdx} maxLap={maxLap} />
      </div>

      {/* STINT PROJECTION */}
      <div style={{
        padding: '8px 14px',
        background: 'var(--panel-header)',
        borderTop: '1px solid var(--rule)',
      }}>
        <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: 2, marginBottom: 6, fontFamily: 'var(--mono)' }}>
          STINT MODEL · PROJECTION
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            { label: 'NEXT LAP', value: fmtLapTime(lap.lap_time.mean + 0.02 * lapNumber), hint: 'ESTIMATED' },
            { label: 'STINT END', value: fmtLapTime(lap.lap_time.mean + 0.025 * (maxLap - lapNumber)), hint: 'PROJECTED' },
            { label: 'AVG WEAR', value: `${avgWearPct}%`, hint: currentWear.toFixed(1) + ' MJ', color: Number(avgWearPct) > 70 ? 'var(--hot)' : Number(avgWearPct) > 45 ? 'var(--warn)' : 'var(--ok)' },
            { label: 'CLIFF IN', value: cliffIn > 50 ? '>50L' : `${cliffIn}L`, hint: 'LAPS', color: cliffColor },
          ].map(({ label, value, hint, color }) => (
            <div key={label} style={{
              background: 'var(--panel)', border: '1px solid var(--rule)', padding: '7px 9px',
            }}>
              <div style={{ fontSize: 8.5, color: 'var(--text-muted)', letterSpacing: 2, fontFamily: 'var(--mono)' }}>{label}</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: color ?? 'var(--text)', letterSpacing: 0.5, fontFamily: 'var(--mono)' }}>
                {value}
              </div>
              <div style={{ fontSize: 8.5, color: 'var(--text-muted)', letterSpacing: 1, fontFamily: 'var(--mono)' }}>{hint}</div>
            </div>
          ))}
        </div>
      </div>

      {/* STATUS LOG (VIZ-07) */}
      <StatusLog laps={revealedLaps} />
    </div>
  )
}
