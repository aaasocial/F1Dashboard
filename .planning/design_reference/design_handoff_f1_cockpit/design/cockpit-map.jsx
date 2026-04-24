/* global React, F1Data */
// Cockpit · Map panel — Bahrain outline + running car dot.
// Viewer version (default): just the dot running around the track.
// Nav version: corners are clickable and filter everything downstream.

const { useMemo } = React;
const { TRACK_POINTS, SECTOR_BOUNDS, TURNS, LAPS } = F1Data;

function MapPanel({ lap, lapNumber, lapFrac, hoveredTurn, setHoveredTurn, race, driver }) {
  const carColor = driver?.teamColor || "#DC0000";
  const circuitName = race?.circuit?.split(/[ ·]/)[0]?.toUpperCase() || "BAHRAIN";
  const circuitKm = race?.km || 5.412;
  const turnCount = race?.turnCount || 15;
  // Car position along track — sample TRACK_POINTS at lapFrac.
  const pts = TRACK_POINTS;
  const sampleIdx = lapFrac * (pts.length - 1);
  const i0 = Math.floor(sampleIdx);
  const i1 = (i0 + 1) % pts.length;
  const t = sampleIdx - i0;
  const [px, py] = [
    pts[i0][0] * (1 - t) + pts[i1][0] * t,
    pts[i0][1] * (1 - t) + pts[i1][1] * t,
  ];
  // Heading (for dot orientation)
  const [pxNext, pyNext] = [
    pts[(i0 + 2) % pts.length][0],
    pts[(i0 + 2) % pts.length][1],
  ];
  const heading = Math.atan2(pyNext - py, pxNext - px);

  return (
    <div style={{
      height: "100%", display: "grid", gridTemplateRows: "38px 1fr", minHeight: 0,
    }}>
      <MapHeader lapNumber={lapNumber} lapFrac={lapFrac} circuitName={circuitName}/>
      <div style={{ position: "relative", background: "radial-gradient(ellipse at center, #06090f 0%, var(--panel-bg) 70%)", overflow: "hidden" }}>
        <svg viewBox="0 0 1 1" preserveAspectRatio="xMidYMid meet"
          style={{ width: "100%", height: "100%", display: "block" }}>
          <defs>
            <pattern id="map-grid" width="0.05" height="0.05" patternUnits="userSpaceOnUse">
              <path d="M 0.05 0 L 0 0 0 0.05" fill="none" stroke="var(--rule)" strokeWidth="0.0005" opacity="0.5"/>
            </pattern>
            <filter id="dot-glow">
              <feGaussianBlur stdDeviation="0.004"/>
              <feMerge>
                <feMergeNode/><feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>

          <rect width="1" height="1" fill="url(#map-grid)"/>

          {/* Track outer glow */}
          <path
            d={trackPath(pts)}
            fill="none"
            stroke="var(--accent)"
            strokeOpacity="0.15"
            strokeWidth="0.028"
          />

          {/* Track sectors in 3 slightly different shades */}
          {SECTOR_BOUNDS.map(([a, b], i) => {
            const sub = pts.slice(a, b + 1);
            if (sub.length < 2) return null;
            const opacity = 0.85 - i * 0.1;
            return (
              <path key={i}
                d={trackPath(sub, false)}
                fill="none"
                stroke={i === 0 ? "#3a98b4" : i === 1 ? "#2a7a93" : "#1d6278"}
                strokeWidth="0.015"
                strokeLinejoin="round"
                strokeLinecap="round"
                opacity={opacity}
              />
            );
          })}

          {/* Centerline */}
          <path
            d={trackPath(pts)}
            fill="none"
            stroke="rgba(232,238,247,0.12)"
            strokeWidth="0.0015"
            strokeDasharray="0.004 0.006"
          />

          {/* Sector boundary markers */}
          {SECTOR_BOUNDS.map(([a], i) => {
            if (i === 0) return null;
            const [x, y] = pts[a];
            return (
              <g key={i}>
                <circle cx={x} cy={y} r="0.008" fill="var(--warn)"/>
                <text x={x} y={y - 0.018}
                  fill="var(--warn)" fontFamily="var(--mono)" fontSize="0.018"
                  textAnchor="middle" letterSpacing="0.001" fontWeight="600">
                  S{i+1}
                </text>
              </g>
            );
          })}

          {/* Turn numbers */}
          {TURNS.map(tu => {
            const idx = Math.round(tu.at * (pts.length - 1));
            const [x, y] = pts[idx];
            return (
              <g key={tu.n} opacity="0.7">
                <circle cx={x} cy={y} r="0.006" fill="var(--text-dim)"/>
                <text x={x} y={y - 0.012}
                  fill="var(--text-dim)" fontFamily="var(--mono)" fontSize="0.013"
                  textAnchor="middle" letterSpacing="0.001">
                  T{tu.n}
                </text>
              </g>
            );
          })}

          {/* Start/finish line */}
          {(() => {
            const [x, y] = pts[0];
            return (
              <g>
                <rect x={x - 0.012} y={y - 0.003} width="0.024" height="0.006"
                  fill="url(#sf-stripes)"/>
                <defs>
                  <pattern id="sf-stripes" width="0.004" height="0.006" patternUnits="userSpaceOnUse">
                    <rect width="0.002" height="0.006" fill="#fff"/>
                    <rect x="0.002" width="0.002" height="0.006" fill="#000"/>
                  </pattern>
                </defs>
                <text x={x} y={y - 0.012}
                  fill="#fff" fontFamily="var(--mono)" fontSize="0.016"
                  textAnchor="middle" letterSpacing="0.002" fontWeight="700">
                  S/F
                </text>
              </g>
            );
          })()}

          {/* Car trail (last ~25% of lap, fading) */}
          <CarTrail pts={pts} lapFrac={lapFrac} color={carColor}/>

          {/* Car dot */}
          <g filter="url(#dot-glow)">
            <circle cx={px} cy={py} r="0.014" fill={carColor} opacity="0.3"/>
            <circle cx={px} cy={py} r="0.008" fill={carColor}/>
            <circle cx={px} cy={py} r="0.004" fill="#fff"/>
            {/* Heading indicator */}
            <line
              x1={px} y1={py}
              x2={px + Math.cos(heading) * 0.025}
              y2={py + Math.sin(heading) * 0.025}
              stroke={carColor} strokeWidth="0.002"
            />
          </g>
        </svg>

        {/* Corner radii / compass */}
        <div style={{
          position: "absolute", top: 8, left: 10,
          fontFamily: "var(--mono)", fontSize: 8.5, letterSpacing: 1.5, color: "var(--text-muted)",
          display: "flex", flexDirection: "column", gap: 1,
        }}>
          <div>{circuitName} · {circuitKm} km · {turnCount}T</div>
          <div style={{ color: "var(--text-dim)" }}>CW · START/FIN ↗</div>
        </div>

        {/* Live speed/sector HUD bottom right */}
        <HUD lap={lap} lapFrac={lapFrac}/>
      </div>
    </div>
  );
}

function MapHeader({ lapNumber, lapFrac, circuitName = "BAHRAIN" }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "0 14px",
      background: "var(--panel-header)",
      borderBottom: "1px solid var(--rule)",
      height: 38,
      fontFamily: "var(--mono)",
      fontSize: 10,
      letterSpacing: 2,
      color: "var(--text-dim)",
    }}>
      <div style={{ width: 2, height: 14, background: "var(--accent)" }}/>
      <span style={{ color: "var(--text)", fontWeight: 700 }}>TRACK</span>
      <span style={{ color: "var(--text-muted)" }}>·</span>
      <span>{circuitName} INTL · POSITION</span>
      <span style={{ flex: 1 }}/>
      <span>L{String(lapNumber).padStart(2,"0")} {(lapFrac*100).toFixed(0)}%</span>
    </div>
  );
}

function trackPath(pts, close = true) {
  if (!pts || pts.length === 0) return "";
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    d += ` L ${pts[i][0]} ${pts[i][1]}`;
  }
  if (close) d += " Z";
  return d;
}

function CarTrail({ pts, lapFrac, color = "#DC0000" }) {
  // Draw a fading trail for the last ~20% of lapFrac worth of track.
  const tailFrac = 0.2;
  const curIdx = lapFrac * (pts.length - 1);
  const startIdx = Math.max(0, curIdx - tailFrac * (pts.length - 1));
  const idxs = [];
  for (let i = Math.floor(startIdx); i <= Math.floor(curIdx); i++) idxs.push(i);
  if (idxs.length < 2) return null;
  return (
    <g>
      {idxs.map((ix, i) => {
        if (i === 0) return null;
        const p0 = pts[idxs[i-1]];
        const p1 = pts[ix];
        const alpha = (i / idxs.length) ** 2;
        return (
          <line key={ix}
            x1={p0[0]} y1={p0[1]}
            x2={p1[0]} y2={p1[1]}
            stroke={color} strokeWidth="0.004"
            strokeLinecap="round" opacity={alpha * 0.85}
          />
        );
      })}
    </g>
  );
}

function HUD({ lap, lapFrac }) {
  // Synthesized "speed" from lapFrac for visual purposes
  // quick/dirty: sin-based profile through lap
  const pseudoSpeed = 160 + 140 * (0.5 + 0.5 * Math.sin(lapFrac * Math.PI * 4.3));
  const throttle = Math.max(0, Math.min(1, 0.6 + 0.4 * Math.cos(lapFrac * Math.PI * 4.3)));
  const brake = Math.max(0, 1 - throttle - 0.3);
  const sectorIdx = lapFrac < 0.33 ? 0 : lapFrac < 0.66 ? 1 : 2;

  return (
    <div style={{
      position: "absolute", bottom: 10, right: 12,
      padding: "8px 10px",
      background: "rgba(7, 10, 17, 0.82)",
      border: "1px solid var(--rule)",
      fontFamily: "var(--mono)", fontSize: 10,
      color: "var(--text-dim)", letterSpacing: 1.2,
      minWidth: 150,
      backdropFilter: "blur(4px)",
    }}>
      <div style={{ fontSize: 8.5, color: "var(--text-muted)", letterSpacing: 2, marginBottom: 4 }}>
        LIVE · SECTOR {sectorIdx + 1}
      </div>
      <div style={{
        fontSize: 24, color: "var(--text)", fontWeight: 600, letterSpacing: 0.5,
      }}>
        {pseudoSpeed.toFixed(0)}<span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: 3 }}>kph</span>
      </div>
      <div style={{ display: "flex", gap: 3, marginTop: 6 }}>
        <MiniBar label="THR" value={throttle} color="var(--ok)"/>
        <MiniBar label="BRK" value={brake} color="var(--hot)"/>
      </div>
    </div>
  );
}

function MiniBar({ label, value, color }) {
  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 7.5, letterSpacing: 1, color: "var(--text-muted)" }}>{label}</div>
      <div style={{ height: 3, background: "var(--rule-strong)", marginTop: 2 }}>
        <div style={{ height: "100%", width: `${value*100}%`, background: color }}/>
      </div>
    </div>
  );
}

window.CockpitMap = { Panel: MapPanel };
