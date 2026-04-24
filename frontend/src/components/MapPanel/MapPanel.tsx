import { useSimulationStore } from '../../stores/useSimulationStore'
import { useUIStore } from '../../stores/useUIStore'
import { lapFracToTrackIndex } from '../../lib/track'
import { PanelHeader } from '../shared/PanelHeader'
import { PanelSkeleton } from '../shared/Skeleton'

export function MapPanel() {
  const data = useSimulationStore(s => s.data)
  const hoveredLap = useUIStore(s => s.hoveredLap)
  const pos = useUIStore(s => s.pos)

  // Use hoveredLap if set, else derive from pos
  const lapIdx = hoveredLap != null
    ? Math.max(0, hoveredLap - 1)
    : Math.min((data?.laps.length ?? 1) - 1, Math.max(0, Math.floor(pos - 1)))
  const lapFrac = pos - Math.floor(pos)

  const track = data?.track ?? []
  const sectorBounds = data?.sectorBounds ?? []
  const turns = data?.turns ?? []
  const teamColor = data?.meta.driver.teamColor ?? '#DC0000'

  // Car position: index proportional to lapFrac around circuit
  const carTrackIdx = Math.floor(lapFrac * Math.max(1, track.length - 1))
  const carPt = track[carTrackIdx] ?? [0.5, 0.5] as [number, number]

  // Car heading: look one point ahead for direction indicator
  const nextIdx = (carTrackIdx + 2) % Math.max(1, track.length)
  const nextPt = track[nextIdx] ?? carPt
  const heading = Math.atan2(nextPt[1] - carPt[1], nextPt[0] - carPt[0])

  // Car trail: last 20% of circuit up to current position (quadratic alpha fade)
  const tailLen = Math.floor(track.length * 0.2)
  const trailStartIdx = Math.max(0, carTrackIdx - tailLen)
  const trailIdxs: number[] = []
  for (let i = trailStartIdx; i <= carTrackIdx; i++) trailIdxs.push(i)

  // Sector splits based on sectorBounds index pairs
  const s1pts = sectorBounds[0]
    ? track.slice(sectorBounds[0][0], sectorBounds[0][1] + 1)
    : track.slice(0, Math.floor(track.length / 3))
  const s2pts = sectorBounds[1]
    ? track.slice(sectorBounds[1][0], sectorBounds[1][1] + 1)
    : track.slice(Math.floor(track.length / 3), Math.floor(2 * track.length / 3))
  const s3pts = sectorBounds[2]
    ? track.slice(sectorBounds[2][0], sectorBounds[2][1] + 1)
    : track.slice(Math.floor(2 * track.length / 3))

  // Current sector (1-indexed) based on car position
  const currentSector = carTrackIdx < Math.floor(track.length / 3)
    ? 1
    : carTrackIdx < Math.floor(2 * track.length / 3)
    ? 2
    : 3

  // Pseudo-speed for HUD (sin-based profile — real telemetry comes from backend in Phase 8)
  const pseudoSpeed = Math.round(160 + 140 * (0.5 + 0.5 * Math.sin(lapFrac * Math.PI * 4.3)))
  const throttle = Math.max(0, Math.min(1, 0.6 + 0.4 * Math.cos(lapFrac * Math.PI * 4.3)))
  const brake = Math.max(0, 1 - throttle - 0.3)

  if (!data) {
    return <PanelSkeleton label="MAP — SELECT STINT AND RUN MODEL" />
  }

  const circuitName = data.meta.race.circuit?.split(/[ ·]/)[0]?.toUpperCase() ?? 'CIRCUIT'

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <PanelHeader
        title="TRACK"
        subtitle={`${circuitName} INTL · POSITION`}
        right={<span>L{String(lapIdx + 1).padStart(2, '0')} {(lapFrac * 100).toFixed(0)}%</span>}
      />
      <div style={{
        flex: 1,
        position: 'relative',
        overflow: 'hidden',
        minHeight: 0,
        background: 'radial-gradient(ellipse at center, #06090f 0%, var(--panel-bg) 70%)',
      }}>
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="xMidYMid meet"
          style={{ width: '100%', height: '100%', display: 'block' }}
        >
          <defs>
            <pattern id="map-grid" width="0.05" height="0.05" patternUnits="userSpaceOnUse">
              <path
                d="M 0.05 0 L 0 0 0 0.05"
                fill="none"
                stroke="var(--rule)"
                strokeWidth="0.0005"
                opacity="0.5"
              />
            </pattern>
            {/* Car dot glow filter */}
            <filter id="dot-glow">
              <feGaussianBlur stdDeviation="0.004" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Start/finish line checker pattern */}
            <pattern id="sf-stripes" width="0.004" height="0.006" patternUnits="userSpaceOnUse">
              <rect width="0.002" height="0.006" fill="#fff" />
              <rect x="0.002" width="0.002" height="0.006" fill="#000" />
            </pattern>
          </defs>

          <rect width="1" height="1" fill="url(#map-grid)" />

          {/* Accent glow under track */}
          {track.length > 1 && (
            <polyline
              points={track.map(p => `${p[0]},${p[1]}`).join(' ')}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="0.028"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.15"
            />
          )}

          {/* Track — 3 sector colors with opacity stepped down */}
          {([s1pts, s2pts, s3pts] as [number, number][][]).map((spts, si) => {
            const colors = ['#3a98b4', '#2a7a93', '#1d6278']
            const opacities = [0.85, 0.75, 0.65]
            if (spts.length < 2) return null
            return (
              <polyline
                key={si}
                points={spts.map(p => `${p[0]},${p[1]}`).join(' ')}
                fill="none"
                stroke={colors[si]}
                strokeWidth="0.015"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={opacities[si]}
              />
            )
          })}

          {/* Dashed centerline */}
          {track.length > 1 && (
            <polyline
              points={track.map(p => `${p[0]},${p[1]}`).join(' ')}
              fill="none"
              stroke="rgba(232,238,247,0.12)"
              strokeWidth="0.0015"
              strokeDasharray="0.004 0.006"
            />
          )}

          {/* Sector boundary markers: skip S1 start (it's the S/F line), show S2, S3 */}
          {[1, 2].map(si => {
            const idx = sectorBounds[si]?.[0] ?? 0
            const pt = track[idx]
            if (!pt) return null
            return (
              <g key={si}>
                <circle cx={pt[0]} cy={pt[1]} r="0.008" fill="var(--warn)" />
                <text
                  x={pt[0]}
                  y={pt[1] - 0.018}
                  fill="var(--warn)"
                  fontFamily="var(--mono)"
                  fontSize="0.018"
                  textAnchor="middle"
                  letterSpacing="0.001"
                  fontWeight="600"
                >
                  S{si + 1}
                </text>
              </g>
            )
          })}

          {/* Turn number labels */}
          {turns.map(turn => {
            const idx = lapFracToTrackIndex(track.length, turn.at)
            const pt = track[idx]
            if (!pt) return null
            return (
              <g key={turn.n} opacity="0.7">
                <circle cx={pt[0]} cy={pt[1]} r="0.006" fill="var(--text-dim)" />
                <text
                  x={pt[0]}
                  y={pt[1] - 0.012}
                  fill="var(--text-dim)"
                  fontFamily="var(--mono)"
                  fontSize="0.013"
                  textAnchor="middle"
                  letterSpacing="0.001"
                >
                  T{turn.n}
                </text>
              </g>
            )
          })}

          {/* Start/finish line at track[0] */}
          {track.length > 0 && (() => {
            const [x, y] = track[0]
            return (
              <g>
                <rect
                  x={x - 0.012}
                  y={y - 0.003}
                  width="0.024"
                  height="0.006"
                  fill="url(#sf-stripes)"
                />
                <text
                  x={x}
                  y={y - 0.012}
                  fill="#fff"
                  fontFamily="var(--mono)"
                  fontSize="0.016"
                  textAnchor="middle"
                  letterSpacing="0.002"
                  fontWeight="700"
                >
                  S/F
                </text>
              </g>
            )
          })()}

          {/* Car trail — last 20% of circuit, quadratic alpha fade */}
          {trailIdxs.length > 1 && trailIdxs.map((ix, i) => {
            if (i === 0) return null
            const p0 = track[trailIdxs[i - 1]]
            const p1 = track[ix]
            if (!p0 || !p1) return null
            const alpha = (i / trailIdxs.length) ** 2 * 0.85
            return (
              <line
                key={ix}
                x1={p0[0]}
                y1={p0[1]}
                x2={p1[0]}
                y2={p1[1]}
                stroke={teamColor}
                strokeWidth="0.004"
                strokeLinecap="round"
                opacity={alpha}
              />
            )
          })}

          {/* Car dot — 3 concentric circles with glow filter */}
          <g filter="url(#dot-glow)">
            <circle cx={carPt[0]} cy={carPt[1]} r="0.014" fill={teamColor} opacity="0.3" />
            <circle cx={carPt[0]} cy={carPt[1]} r="0.008" fill={teamColor} />
            <circle cx={carPt[0]} cy={carPt[1]} r="0.004" fill="#ffffff" />
            {/* Heading indicator line */}
            <line
              x1={carPt[0]}
              y1={carPt[1]}
              x2={carPt[0] + Math.cos(heading) * 0.025}
              y2={carPt[1] + Math.sin(heading) * 0.025}
              stroke={teamColor}
              strokeWidth="0.002"
            />
          </g>

          {/* Top-left circuit info overlay */}
          <g>
            <text
              x="0.03"
              y="0.05"
              fill="var(--text-muted)"
              fontSize="0.0085"
              fontFamily="var(--mono)"
              letterSpacing="0.0015"
            >
              {circuitName} · {(data.meta.race as { km?: number }).km ?? 5.412} km
            </text>
            <text
              x="0.03"
              y="0.065"
              fill="var(--text-dim)"
              fontSize="0.008"
              fontFamily="var(--mono)"
            >
              CW · START/FIN ↗
            </text>
          </g>
        </svg>

        {/* HUD — bottom-right: sector, speed, THR/BRK bars */}
        <div style={{
          position: 'absolute',
          bottom: 10,
          right: 12,
          padding: '8px 10px',
          background: 'rgba(7, 10, 17, 0.82)',
          border: '1px solid var(--rule)',
          fontFamily: 'var(--mono)',
          fontSize: 10,
          color: 'var(--text-dim)',
          letterSpacing: 1.2,
          minWidth: 150,
          backdropFilter: 'blur(4px)',
        }}>
          <div style={{
            fontSize: 8.5,
            color: 'var(--text-muted)',
            letterSpacing: 2,
            marginBottom: 4,
          }}>
            LIVE · SECTOR {currentSector}
          </div>
          <div style={{
            fontSize: 24,
            color: 'var(--text)',
            fontWeight: 600,
            letterSpacing: 0.5,
          }}>
            {pseudoSpeed}
            <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 3 }}>kph</span>
          </div>
          <div style={{ display: 'flex', gap: 3, marginTop: 6 }}>
            {/* THR bar */}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 7.5, letterSpacing: 1, color: 'var(--text-muted)' }}>THR</div>
              <div style={{ height: 3, background: 'var(--rule-strong)', marginTop: 2 }}>
                <div style={{ height: '100%', width: `${throttle * 100}%`, background: 'var(--ok)' }} />
              </div>
            </div>
            {/* BRK bar */}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 7.5, letterSpacing: 1, color: 'var(--text-muted)' }}>BRK</div>
              <div style={{ height: 3, background: 'var(--rule-strong)', marginTop: 2 }}>
                <div style={{ height: '100%', width: `${brake * 100}%`, background: 'var(--hot)' }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
