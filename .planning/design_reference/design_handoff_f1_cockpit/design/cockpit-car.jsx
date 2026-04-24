/* global React, F1Data */
// Cockpit · Car panel — top-down schematic with integrated tire/brake/wear data.
// Aesthetic: Mercedes/Red Bull engineering — monochrome chassis, data painted on geometry.
//
// Layout:
//  ┌─ header: "CAR · SF-24 · TOP-DOWN"
//  ├─ main SVG: vertical top-down car (nose up), 4 tires, 4 brake discs, wings, floor
//  │     tires colored by tread temp (viridis)
//  │     brake discs glow amber with brake temp
//  │     wear shown as tread-block erosion (thin bands removed)
//  │     grip shown as outboard ring segments
//  │     slip angle = small arc indicator on each tire
//  └─ footer: small per-corner readouts + legend

const { useState, useEffect, useRef } = React;
const { META, LAPS, tempToViridis, CORNER_COLORS, CORNER_LABELS, COMPOUND_COLORS } = F1Data;

// Derived values ---------------------------------------------------------
function brakeTemp(lap, c) {
  // synthetic from slip + wear — fronts run hotter
  const e = lap[`e_tire_${c}`].mean;
  const sl = lap[`slip_angle_${c}`].mean;
  const isFront = c.startsWith("f");
  const base = isFront ? 560 : 410;
  return base + e * 22 + sl * 28;
}
function wearPct(lap, c) {
  return Math.max(0, Math.min(1, lap[`e_tire_${c}`].mean / 22));
}

// SVG geometry: vertical car, 400w × 780h.
// origin: nose at (200, 40), rear at (200, 740).
const CAR = {
  w: 400, h: 780,
  // Tire centers + dims (native)
  tires: {
    fl: { cx: 82,  cy: 240, w: 46, h: 78,  isFront: true,  isLeft: true  },
    fr: { cx: 318, cy: 240, w: 46, h: 78,  isFront: true,  isLeft: false },
    rl: { cx: 76,  cy: 600, w: 54, h: 96,  isFront: false, isLeft: true  },
    rr: { cx: 324, cy: 600, w: 54, h: 96,  isFront: false, isLeft: false },
  },
};

function CarPanel({ lap, lapNumber, lapFrac, hoveredCorner, setHoveredCorner, stint }) {
  const compound = stint?.compound || META.stint.compound;
  const compoundColor = COMPOUND_COLORS[compound] || "#FFD700";

  return (
    <div style={{
      height: "100%",
      display: "grid",
      gridTemplateRows: "38px 1fr auto",
      minHeight: 0,
    }}>
      <CarHeader lapNumber={lapNumber}/>

      {/* Main SVG canvas */}
      <div style={{
        position: "relative",
        overflow: "hidden",
        minHeight: 0,
        background: "radial-gradient(ellipse at center, #0a1018 0%, var(--panel-bg) 70%)",
      }}>
        <svg
          viewBox={`0 0 ${CAR.w} ${CAR.h}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ width: "100%", height: "100%", display: "block" }}
        >
          <defs>
            {/* Grid pattern — technical backdrop */}
            <pattern id="tech-grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="var(--rule)" strokeWidth="0.3" opacity="0.6"/>
            </pattern>
            {/* Brake glow */}
            <radialGradient id="brake-glow">
              <stop offset="0%" stopColor="#FFB020" stopOpacity="0.9"/>
              <stop offset="60%" stopColor="#FF6A00" stopOpacity="0.4"/>
              <stop offset="100%" stopColor="#FF3300" stopOpacity="0"/>
            </radialGradient>
          </defs>

          <rect width={CAR.w} height={CAR.h} fill="url(#tech-grid)"/>

          {/* Centerline */}
          <line x1={CAR.w/2} y1="10" x2={CAR.w/2} y2={CAR.h-10}
            stroke="var(--rule-strong)" strokeWidth="0.5" strokeDasharray="3 5" opacity="0.5"/>

          {/* Axle reference lines */}
          <g opacity="0.35">
            <line x1="30" y1={CAR.tires.fl.cy} x2={CAR.w-30} y2={CAR.tires.fl.cy}
              stroke="var(--rule-strong)" strokeWidth="0.5" strokeDasharray="2 4"/>
            <line x1="20" y1={CAR.tires.rl.cy} x2={CAR.w-20} y2={CAR.tires.rl.cy}
              stroke="var(--rule-strong)" strokeWidth="0.5" strokeDasharray="2 4"/>
            <text x={CAR.w-28} y={CAR.tires.fl.cy-4} fill="var(--text-muted)"
              fontFamily="var(--mono)" fontSize="7" letterSpacing="1.2" textAnchor="end">FRONT AXLE</text>
            <text x={CAR.w-28} y={CAR.tires.rl.cy-4} fill="var(--text-muted)"
              fontFamily="var(--mono)" fontSize="7" letterSpacing="1.2" textAnchor="end">REAR AXLE</text>
          </g>

          {/* ── Chassis outline ── */}
          <CarChassis/>

          {/* ── Tires + brakes + wheel data ── */}
          {Object.entries(CAR.tires).map(([c, geom]) => (
            <CarWheel key={c}
              corner={c}
              geom={geom}
              lap={lap}
              hovered={hoveredCorner === c}
              onHover={setHoveredCorner}
            />
          ))}

          {/* Compound strip at top */}
          <g transform="translate(140, 18)">
            <rect width="120" height="3" fill={compoundColor}/>
            <text x="60" y="15" fill="var(--text-dim)" fontFamily="var(--mono)"
              fontSize="8" textAnchor="middle" letterSpacing="2">
              {compound} · AGE {lapNumber}
            </text>
          </g>

          {/* Dimension annotations */}
          <g fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="7" letterSpacing="1">
            {/* wheelbase */}
            <line x1="360" y1={CAR.tires.fl.cy} x2="360" y2={CAR.tires.rl.cy}
              stroke="var(--text-muted)" strokeWidth="0.5"/>
            <line x1="356" y1={CAR.tires.fl.cy} x2="364" y2={CAR.tires.fl.cy}
              stroke="var(--text-muted)" strokeWidth="0.5"/>
            <line x1="356" y1={CAR.tires.rl.cy} x2="364" y2={CAR.tires.rl.cy}
              stroke="var(--text-muted)" strokeWidth="0.5"/>
            <text x="368" y={(CAR.tires.fl.cy + CAR.tires.rl.cy)/2 + 2}>WB 3600</text>

            {/* front track */}
            <line x1={CAR.tires.fl.cx} y1="200" x2={CAR.tires.fr.cx} y2="200"
              stroke="var(--text-muted)" strokeWidth="0.5"/>
            <text x={CAR.w/2} y="196" textAnchor="middle">TRACK 2000</text>
          </g>
        </svg>
      </div>

      <CarFooterReadouts lap={lap} hoveredCorner={hoveredCorner} setHoveredCorner={setHoveredCorner}/>
    </div>
  );
}

function CarHeader({ lapNumber }) {
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
      <span style={{ color: "var(--text)", fontWeight: 700 }}>CAR</span>
      <span style={{ color: "var(--text-muted)" }}>·</span>
      <span>SF-24 · TOP-DOWN · INTEGRATED TELEMETRY</span>
      <span style={{ flex: 1 }}/>
      <span>LAP {String(lapNumber).padStart(2, "0")}</span>
    </div>
  );
}

// ── Chassis outline ─────────────────────────────────────────────────────
// Simplified SF-24 top-down silhouette. Single-color line art.
function CarChassis() {
  const stroke = "var(--rule-strong)";
  const hi = "var(--text-muted)";
  return (
    <g fill="none" stroke={stroke} strokeWidth="1.1" strokeLinejoin="round" strokeLinecap="round">
      {/* Front wing */}
      <path d="M 60 130 L 340 130 L 340 138 L 60 138 Z" fill="var(--panel)" opacity="0.6"/>
      <line x1="60" y1="134" x2="340" y2="134" stroke={hi} strokeWidth="0.5" opacity="0.8"/>
      {/* Front wing endplates */}
      <rect x="56" y="126" width="8" height="22" fill="var(--panel)" stroke={stroke}/>
      <rect x="336" y="126" width="8" height="22" fill="var(--panel)" stroke={stroke}/>

      {/* Nose cone */}
      <path d="M 185 148 L 185 210 L 215 210 L 215 148 Q 215 140 200 140 Q 185 140 185 148 Z"
        fill="var(--panel)"/>

      {/* Front suspension arms (FL) */}
      <line x1="130" y1={230} x2="185" y2="195" stroke={stroke} strokeWidth="1"/>
      <line x1="130" y1={250} x2="185" y2="215" stroke={stroke} strokeWidth="1"/>
      {/* (FR) */}
      <line x1="270" y1={230} x2="215" y2="195" stroke={stroke} strokeWidth="1"/>
      <line x1="270" y1={250} x2="215" y2="215" stroke={stroke} strokeWidth="1"/>

      {/* Main chassis tub */}
      <path d="M 175 210 L 175 440 Q 175 460 190 460 L 210 460 Q 225 460 225 440 L 225 210 Z"
        fill="var(--panel)" stroke={stroke}/>

      {/* Halo */}
      <ellipse cx={200} cy={310} rx="18" ry="14" fill="none" stroke={hi} strokeWidth="0.8"/>
      <line x1="200" y1="296" x2="200" y2="330" stroke={hi} strokeWidth="0.6"/>

      {/* Cockpit */}
      <ellipse cx={200} cy={315} rx="13" ry="22" fill="#050810" stroke={stroke} strokeWidth="0.8"/>

      {/* Sidepods */}
      <path d="M 140 320 Q 135 340 140 360 L 150 440 Q 155 455 175 455 L 175 380 Q 170 340 155 320 Z"
        fill="var(--panel)" stroke={stroke}/>
      <path d="M 260 320 Q 265 340 260 360 L 250 440 Q 245 455 225 455 L 225 380 Q 230 340 245 320 Z"
        fill="var(--panel)" stroke={stroke}/>

      {/* Airbox */}
      <rect x="193" y="240" width="14" height="30" fill="#050810" stroke={hi} strokeWidth="0.6"/>
      <text x="200" y="258" fill={hi} fontFamily="var(--mono)" fontSize="6" textAnchor="middle"
        letterSpacing="0.5">AIRBOX</text>

      {/* Engine / gearbox area */}
      <rect x="180" y="460" width="40" height="120" fill="var(--panel)" stroke={stroke}/>
      <line x1="180" y1="480" x2="220" y2="480" stroke={stroke} strokeWidth="0.5" opacity="0.7"/>
      <line x1="180" y1="500" x2="220" y2="500" stroke={stroke} strokeWidth="0.5" opacity="0.7"/>
      <line x1="180" y1="520" x2="220" y2="520" stroke={stroke} strokeWidth="0.5" opacity="0.7"/>
      <line x1="180" y1="540" x2="220" y2="540" stroke={stroke} strokeWidth="0.5" opacity="0.7"/>
      <line x1="180" y1="560" x2="220" y2="560" stroke={stroke} strokeWidth="0.5" opacity="0.7"/>

      {/* Floor */}
      <path d="M 130 280 L 270 280 L 275 650 L 125 650 Z" fill="none" stroke={hi} strokeWidth="0.4"
        strokeDasharray="2 3" opacity="0.6"/>

      {/* Rear suspension arms */}
      <line x1="130" y1="580" x2="180" y2="600" stroke={stroke} strokeWidth="1"/>
      <line x1="130" y1="620" x2="180" y2="640" stroke={stroke} strokeWidth="1"/>
      <line x1="270" y1="580" x2="220" y2="600" stroke={stroke} strokeWidth="1"/>
      <line x1="270" y1="620" x2="220" y2="640" stroke={stroke} strokeWidth="1"/>

      {/* Rear wing */}
      <path d="M 110 670 L 290 670 L 290 680 L 110 680 Z" fill="var(--panel)"/>
      <rect x="106" y="660" width="8" height="30" fill="var(--panel)" stroke={stroke}/>
      <rect x="286" y="660" width="8" height="30" fill="var(--panel)" stroke={stroke}/>
      {/* DRS line */}
      <line x1="110" y1="674" x2="290" y2="674" stroke={hi} strokeWidth="0.5"/>
      <text x={CAR.w/2} y="700" fill={hi} fontFamily="var(--mono)" fontSize="7" textAnchor="middle"
        letterSpacing="1.5">REAR WING · DRS</text>

      {/* Diffuser hint */}
      <path d="M 145 710 L 170 740 M 175 712 L 190 745 M 200 712 L 200 748 M 225 712 L 210 745 M 255 710 L 230 740"
        stroke={hi} strokeWidth="0.5" opacity="0.7"/>

      {/* Forward arrow / heading */}
      <g opacity="0.45">
        <line x1="200" y1="90" x2="200" y2="118" stroke="var(--accent)" strokeWidth="1"/>
        <path d="M 195 96 L 200 88 L 205 96 Z" fill="var(--accent)"/>
        <text x="200" y="82" fill="var(--accent)" fontFamily="var(--mono)" fontSize="7"
          textAnchor="middle" letterSpacing="2">DIR</text>
      </g>
    </g>
  );
}

// ── Wheel: tire + brake + wear + grip + slip ───────────────────────────
function CarWheel({ corner, geom, lap, hovered, onHover }) {
  const temp = lap[`t_tread_${corner}`].mean;
  const tempLo = lap[`t_tread_${corner}`].lo_95;
  const tempHi = lap[`t_tread_${corner}`].hi_95;
  const grip = lap[`grip_${corner}`].mean;
  const wear = wearPct(lap, corner);
  const slip = lap[`slip_angle_${corner}`].mean;
  const brakeT = brakeTemp(lap, corner);

  const { cx, cy, w, h, isFront, isLeft } = geom;
  const tempColor = tempToViridis(temp);
  const brakeNorm = Math.max(0, Math.min(1, (brakeT - 300) / 500));

  // Tire rectangle coordinates
  const x = cx - w/2, y = cy - h/2;

  // Tread block count for wear visualization (8 horizontal bands)
  const bands = 8;
  const bandH = h / bands;

  // Grip segments — vertical bars outboard of the tire
  const gripSegs = 10;
  const gripNorm = Math.max(0, Math.min(1, (grip - 1.05) / 0.45));
  const litGrip = Math.round(gripNorm * gripSegs);

  // Slip angle tick — small angled line above the tire
  const slipAngle = Math.max(-6, Math.min(6, slip)) * (isLeft ? -1 : 1);

  // Outboard layout direction
  const outboardX = isLeft ? -1 : 1;
  const gripX = isLeft ? x - 16 : x + w + 2;

  // Wear color
  const wearLevel = wear > 0.7 ? "#FF3344" : wear > 0.45 ? "#FFB020" : "#22E27A";

  return (
    <g
      style={{ cursor: "pointer" }}
      onMouseEnter={() => onHover(corner)}
      onMouseLeave={() => onHover(null)}
    >
      {/* Brake glow behind tire (halo) */}
      <ellipse cx={cx} cy={cy} rx={w * 0.75} ry={h * 0.55}
        fill="url(#brake-glow)"
        opacity={0.25 + brakeNorm * 0.55}/>

      {/* Tire body — outer rim */}
      <rect x={x-1.5} y={y-1.5} width={w+3} height={h+3}
        fill="none"
        stroke={hovered ? "var(--accent)" : "var(--text-muted)"}
        strokeWidth={hovered ? "1.4" : "0.8"}/>

      {/* Tire fill — viridis temp */}
      <rect x={x} y={y} width={w} height={h}
        fill={tempColor} opacity="0.88"/>

      {/* Tread block lines (dark grooves) */}
      {Array.from({ length: bands - 1 }).map((_, i) => (
        <line key={i}
          x1={x} y1={y + (i+1) * bandH}
          x2={x+w} y2={y + (i+1) * bandH}
          stroke="rgba(0,0,0,0.45)" strokeWidth="0.8"/>
      ))}

      {/* Wear erosion — blocks at leading edge chewed off by wear */}
      {(() => {
        const erodedBands = Math.round(wear * bands);
        const eLeadFront = isFront;  // fronts wear more on leading edge
        const stripe = [];
        for (let i = 0; i < erodedBands; i++) {
          const byi = eLeadFront ? y + i * bandH : y + h - (i+1) * bandH;
          stripe.push(
            <rect key={i} x={x} y={byi} width={w} height={bandH * 0.85}
              fill="rgba(10,14,21,0.78)"/>
          );
        }
        return stripe;
      })()}

      {/* Temp number centered on tire (with readable contrast) */}
      <g>
        <rect x={cx - 16} y={cy - 9} width="32" height="18" rx="1"
          fill="rgba(0,0,0,0.58)"/>
        <text x={cx} y={cy + 4} fill="#fff" fontFamily="var(--mono)"
          fontSize={isFront ? "11" : "12"} fontWeight="700" textAnchor="middle"
          letterSpacing="0.5">
          {temp.toFixed(0)}°
        </text>
      </g>

      {/* Corner label — inboard side */}
      <text
        x={isLeft ? x + w + 6 : x - 6}
        y={y + 10}
        fill={hovered ? "var(--accent)" : "var(--text)"}
        fontFamily="var(--mono)" fontSize="11" fontWeight="700" letterSpacing="2"
        textAnchor={isLeft ? "start" : "end"}>
        {corner.toUpperCase()}
      </text>

      {/* Grip ladder — outboard, vertical */}
      <g transform={`translate(${gripX}, ${y})`}>
        {Array.from({ length: gripSegs }).map((_, i) => {
          const seg = gripSegs - 1 - i;
          const lit = seg < litGrip;
          return (
            <rect key={i}
              x={0} y={i * (h / gripSegs) + 1}
              width={14} height={h / gripSegs - 2}
              fill={lit ? "var(--accent)" : "var(--rule-strong)"}
              opacity={lit ? (0.4 + 0.6 * (seg / gripSegs)) : 0.5}
            />
          );
        })}
      </g>
      <text x={gripX + 7} y={y - 3}
        fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="7"
        textAnchor="middle" letterSpacing="1">μ</text>
      <text x={gripX + 7} y={y + h + 11}
        fill="var(--accent)" fontFamily="var(--mono)" fontSize="8" fontWeight="600"
        textAnchor="middle">
        {grip.toFixed(2)}
      </text>

      {/* Wear bar — outboard of grip ladder, horizontal under tire */}
      <g transform={`translate(${x}, ${y + h + 4})`}>
        <rect x={0} y={0} width={w} height={3} fill="var(--rule-strong)"/>
        <rect x={0} y={0} width={w * wear} height={3} fill={wearLevel}/>
        <text x={w/2} y={13} fill="var(--text-muted)" fontFamily="var(--mono)"
          fontSize="7" textAnchor="middle" letterSpacing="1">
          WEAR {(wear * 100).toFixed(0)}%
        </text>
      </g>

      {/* Slip angle tick — above tire */}
      <g transform={`translate(${cx}, ${y - 8}) rotate(${slipAngle * 2})`}>
        <line x1="0" y1="0" x2="0" y2="-14"
          stroke={hovered ? "var(--accent)" : "var(--text-dim)"} strokeWidth="1.2"/>
        <circle cx="0" cy="-14" r="1.5" fill={hovered ? "var(--accent)" : "var(--text-dim)"}/>
      </g>
      <text x={cx} y={y - 28} fill="var(--text-muted)" fontFamily="var(--mono)"
        fontSize="7" textAnchor="middle" letterSpacing="0.8">
        α {slip.toFixed(1)}°
      </text>

      {/* Brake temp readout — inboard */}
      <g transform={`translate(${isLeft ? x + w + 6 : x - 6}, ${cy + 8})`}>
        <text textAnchor={isLeft ? "start" : "end"}
          fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="7" letterSpacing="1">BR</text>
        <text y="10" textAnchor={isLeft ? "start" : "end"}
          fill="#FFB020" fontFamily="var(--mono)" fontSize="9" fontWeight="600">
          {brakeT.toFixed(0)}°C
        </text>
      </g>

      {/* CI halo — thin ring around tire showing temp uncertainty */}
      <rect x={x - 2} y={y - 2} width={w+4} height={h+4}
        fill="none"
        stroke={tempColor}
        strokeWidth={0.6 + Math.min(3, (tempHi - tempLo) * 0.12)}
        opacity="0.35"/>

      {/* Hover box outline */}
      {hovered && (
        <rect x={x - 22} y={y - 34} width={w + 44} height={h + 62}
          fill="none" stroke="var(--accent)" strokeWidth="0.7"
          strokeDasharray="3 3" opacity="0.6"/>
      )}
    </g>
  );
}

// ── Footer readouts ────────────────────────────────────────────────────
function CarFooterReadouts({ lap, hoveredCorner, setHoveredCorner }) {
  const corners = ["fl", "fr", "rl", "rr"];

  return (
    <div style={{
      borderTop: "1px solid var(--rule)",
      background: "var(--panel-header)",
      display: "grid",
      gridTemplateColumns: "repeat(4, 1fr)",
      gap: 1,
    }}>
      {corners.map(c => {
        const temp = lap[`t_tread_${c}`].mean;
        const tempLo = lap[`t_tread_${c}`].lo_95;
        const tempHi = lap[`t_tread_${c}`].hi_95;
        const grip = lap[`grip_${c}`].mean;
        const gripCi = (lap[`grip_${c}`].hi_95 - grip);
        const wear = wearPct(lap, c);
        const slip = lap[`slip_angle_${c}`].mean;
        const br = brakeTemp(lap, c);

        const active = hoveredCorner === c;

        return (
          <div key={c}
            onMouseEnter={() => setHoveredCorner(c)}
            onMouseLeave={() => setHoveredCorner(null)}
            style={{
              padding: "8px 10px 10px",
              background: active ? "var(--panel-header-hi)" : "transparent",
              borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
              cursor: "pointer",
              fontFamily: "var(--mono)",
            }}>
            <div style={{
              display: "flex", alignItems: "baseline", gap: 6,
              marginBottom: 4,
            }}>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: 2,
                color: active ? "var(--accent)" : "var(--text)",
              }}>{c.toUpperCase()}</span>
              <span style={{ fontSize: 8, color: "var(--text-muted)", letterSpacing: 1 }}>
                {c.startsWith("f") ? "FRONT" : "REAR"}·{c.endsWith("l") ? "L" : "R"}
              </span>
            </div>
            <CarRow label="T" value={`${temp.toFixed(1)}`} unit="°C"
              ci={`${tempLo.toFixed(0)}–${tempHi.toFixed(0)}`}/>
            <CarRow label="μ" value={grip.toFixed(3)} unit="" ci={`±${gripCi.toFixed(3)}`}
              valueColor="var(--accent)"/>
            <CarRow label="WEAR" value={`${(wear*100).toFixed(1)}`} unit="%"
              valueColor={wear > 0.7 ? "#FF3344" : wear > 0.45 ? "#FFB020" : "var(--text)"}/>
            <CarRow label="α"   value={slip.toFixed(2)} unit="°"/>
            <CarRow label="BRK" value={br.toFixed(0)} unit="°C" valueColor="#FFB020"/>
          </div>
        );
      })}
    </div>
  );
}

function CarRow({ label, value, unit, ci, valueColor = "var(--text)" }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "28px 1fr",
      fontSize: 10, marginTop: 1, alignItems: "baseline",
    }}>
      <span style={{ color: "var(--text-muted)", letterSpacing: 1 }}>{label}</span>
      <span style={{ color: valueColor, textAlign: "right", fontWeight: 600 }}>
        {value}<span style={{ color: "var(--text-muted)", fontSize: 8, marginLeft: 2, fontWeight: 400 }}>{unit}</span>
        {ci && <span style={{ color: "var(--text-muted)", fontSize: 8, marginLeft: 4, fontWeight: 400 }}>{ci}</span>}
      </span>
    </div>
  );
}

window.CockpitCar = { Panel: CarPanel };
