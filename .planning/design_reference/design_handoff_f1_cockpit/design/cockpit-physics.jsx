/* global React, F1Data */
// Cockpit · Physics panel — tabbed per-corner small multiples.
// Tabs: TREAD TEMP · GRIP μ · TREAD WEAR E · SLIP α PEAK
// Based on baseline Zone 4 but re-skinned for the cockpit aesthetic.

const { useState, useEffect, useRef } = React;
const { LAPS, CORNER_COLORS, CORNER_LABELS } = F1Data;

const METRICS = {
  t_tread:    { label: "TREAD TEMP",  unit: "°C", fmt: v => v.toFixed(1), domain: [88, 118], accent: "#FFD700" },
  grip:       { label: "GRIP μ",      unit: "",   fmt: v => v.toFixed(3), domain: [1.10, 1.50], accent: "#00E5FF" },
  e_tire:     { label: "WEAR E",      unit: "MJ", fmt: v => v.toFixed(2), domain: [0, 22],    accent: "#FFB020" },
  slip_angle: { label: "SLIP α PEAK", unit: "°",  fmt: v => v.toFixed(2), domain: [1.5, 5.5], accent: "#A855F7" },
};

function PhysicsPanel({ revealedLaps, lapNumber, hoveredCorner, setHoveredCorner }) {
  const [metric, setMetric] = useState("t_tread");
  const cfg = METRICS[metric];
  const corners = ["fl", "fr", "rl", "rr"];

  return (
    <div style={{
      height: "100%", display: "grid", gridTemplateRows: "38px auto 1fr",
      minHeight: 0,
    }}>
      <PhysicsHeader lapNumber={lapNumber} revealed={revealedLaps.length}/>

      {/* Metric tabs */}
      <div style={{
        display: "flex",
        background: "var(--panel-header)",
        borderBottom: "1px solid var(--rule)",
      }}>
        {Object.entries(METRICS).map(([key, m]) => {
          const active = metric === key;
          return (
            <button key={key}
              onClick={() => setMetric(key)}
              style={{
                flex: 1,
                padding: "7px 10px",
                background: active ? "var(--panel-header-hi)" : "transparent",
                border: "none",
                borderBottom: active ? `2px solid ${m.accent}` : "2px solid transparent",
                color: active ? "var(--text)" : "var(--text-dim)",
                fontFamily: "var(--mono)", fontSize: 9.5, letterSpacing: 1.6,
                fontWeight: active ? 700 : 500,
                textAlign: "left",
              }}>
              {m.label}
              <span style={{ marginLeft: 6, color: "var(--text-muted)", letterSpacing: 1, fontSize: 8 }}>
                {m.unit}
              </span>
            </button>
          );
        })}
      </div>

      {/* Charts */}
      <div style={{
        display: "grid", gridTemplateRows: "repeat(4, 1fr)",
        minHeight: 0,
      }}>
        {corners.map((c, i) => (
          <PhysicsChart
            key={c}
            corner={c}
            metric={metric}
            cfg={cfg}
            revealedLaps={revealedLaps}
            hovered={hoveredCorner === c}
            onHover={setHoveredCorner}
            isLast={i === corners.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

function PhysicsHeader({ lapNumber, revealed }) {
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
      <span style={{ color: "var(--text)", fontWeight: 700 }}>PHYSICS</span>
      <span style={{ color: "var(--text-muted)" }}>·</span>
      <span>LAP-BY-LAP · CI₉₅</span>
      <span style={{ flex: 1 }}/>
      <span>{revealed}/{LAPS.length} LAPS</span>
    </div>
  );
}

function PhysicsChart({ corner, metric, cfg, revealedLaps, hovered, onHover, isLast }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ w: 480, h: 70 });
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) setSize({ w: e.contentRect.width, h: e.contentRect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [hoverLap, setHoverLap] = useState(null);

  const padL = 40, padR = 12, padT = 8, padB = isLast ? 18 : 6;
  const w = size.w, h = size.h;
  const iw = Math.max(10, w - padL - padR);
  const ih = Math.max(10, h - padT - padB);
  const [yMin, yMax] = cfg.domain;
  const xMin = 1, xMax = LAPS.length;

  const sx = (lap) => padL + ((lap - xMin) / (xMax - xMin)) * iw;
  const sy = (v) => padT + (1 - (v - yMin) / (yMax - yMin)) * ih;

  const data = revealedLaps.map(l => ({
    lap: l.lap_number,
    v: l[`${metric}_${corner}`].mean,
    lo: l[`${metric}_${corner}`].lo_95,
    hi: l[`${metric}_${corner}`].hi_95,
  }));

  const meanPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${sx(d.lap).toFixed(1)} ${sy(d.v).toFixed(1)}`).join(" ");
  const ciPath = data.length > 1
    ? data.map((d, i) => `${i === 0 ? "M" : "L"}${sx(d.lap).toFixed(1)} ${sy(d.hi).toFixed(1)}`).join(" ") +
      " " + data.slice().reverse().map(d => `L${sx(d.lap).toFixed(1)} ${sy(d.lo).toFixed(1)}`).join(" ") + " Z"
    : null;

  const color = CORNER_COLORS[corner];

  function onMove(e) {
    const rect = ref.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const lap = Math.round(xMin + ((px - padL) / iw) * (xMax - xMin));
    const maxLap = data.length > 0 ? data[data.length - 1].lap : 0;
    setHoverLap(lap >= 1 && lap <= maxLap ? lap : null);
  }

  const hoverPoint = hoverLap ? data.find(d => d.lap === hoverLap) : null;

  return (
    <div
      ref={ref}
      onMouseEnter={() => onHover(corner)}
      onMouseLeave={() => { onHover(null); setHoverLap(null); }}
      onMouseMove={onMove}
      style={{
        position: "relative",
        background: hovered ? "var(--panel-header-hi)" : "transparent",
        borderBottom: isLast ? "none" : "1px solid var(--rule)",
        borderLeft: hovered ? `2px solid ${color}` : "2px solid transparent",
        cursor: "crosshair",
      }}>
      <svg width={w} height={h} style={{ display: "block" }}>
        {/* grid */}
        {[0, 1/3, 2/3, 1].map((p, i) => (
          <line key={i} x1={padL} y1={padT + ih*p} x2={padL + iw} y2={padT + ih*p}
            stroke="var(--rule)" strokeWidth="0.4" opacity="0.7"/>
        ))}
        {/* vertical lap grid every 5 */}
        {Array.from({ length: LAPS.length }).map((_, i) => {
          const lap = i + 1;
          if (lap % 5 !== 0 && lap !== 1 && lap !== LAPS.length) return null;
          return (
            <line key={lap} x1={sx(lap)} y1={padT} x2={sx(lap)} y2={padT+ih}
              stroke="var(--rule)" strokeWidth="0.3" opacity="0.5"/>
          );
        })}

        {/* CI band */}
        {ciPath && <path d={ciPath} fill={color} opacity="0.12"/>}

        {/* Mean line */}
        <path d={meanPath} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round"/>
        {data.map(d => (
          <circle key={d.lap} cx={sx(d.lap)} cy={sy(d.v)} r="1.6" fill={color}/>
        ))}

        {/* Y ticks */}
        {[yMin, (yMin+yMax)/2, yMax].map((v, i) => (
          <text key={i} x={padL - 4} y={sy(v)+3}
            fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="8"
            textAnchor="end">{cfg.fmt(v)}</text>
        ))}

        {/* Corner label */}
        <g>
          <rect x={padL + 4} y={padT + 2} width="24" height="12"
            fill="rgba(7,10,17,0.85)" stroke={color} strokeWidth="0.6"/>
          <text x={padL + 16} y={padT + 11} fill={color}
            fontFamily="var(--mono)" fontSize="9" fontWeight="700"
            textAnchor="middle" letterSpacing="1">
            {CORNER_LABELS[corner]}
          </text>
        </g>

        {/* Hover crosshair */}
        {hoverPoint && (
          <g>
            <line x1={sx(hoverPoint.lap)} y1={padT} x2={sx(hoverPoint.lap)} y2={padT+ih}
              stroke={color} strokeWidth="0.7" opacity="0.7"/>
            <circle cx={sx(hoverPoint.lap)} cy={sy(hoverPoint.v)} r="3"
              fill={color} stroke="var(--panel-bg)" strokeWidth="1.2"/>
            <g transform={`translate(${Math.min(sx(hoverPoint.lap) + 6, padL + iw - 80)}, ${Math.max(sy(hoverPoint.v) - 16, padT + 2)})`}>
              <rect x="0" y="0" width="76" height="14"
                fill="rgba(7,10,17,0.95)" stroke={color} strokeWidth="0.7"/>
              <text x="4" y="10" fill={color} fontFamily="var(--mono)" fontSize="9">
                L{hoverPoint.lap} {cfg.fmt(hoverPoint.v)}
                <tspan fill="var(--text-muted)" fontSize="7.5" dx="2">
                  ±{cfg.fmt(hoverPoint.hi - hoverPoint.v)}
                </tspan>
              </text>
            </g>
          </g>
        )}

        {/* X axis labels on last chart */}
        {isLast && (
          <g>
            {Array.from({ length: LAPS.length }).map((_, i) => {
              const lap = i + 1;
              if (lap % 5 !== 0 && lap !== 1 && lap !== LAPS.length) return null;
              return (
                <text key={lap} x={sx(lap)} y={h - 4}
                  fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="8"
                  textAnchor="middle">L{lap}</text>
              );
            })}
          </g>
        )}
      </svg>
    </div>
  );
}

window.CockpitPhysics = { Panel: PhysicsPanel };
