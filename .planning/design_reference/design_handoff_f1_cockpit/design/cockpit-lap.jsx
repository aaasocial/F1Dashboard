/* global React, F1Data */
// Cockpit · Lap info panel — middle column.
// Contents (user asked for all of them):
//   - Big current lap time + delta to personal best / to model prediction
//   - Sector bars (S1/S2/S3) with F1 TV color rules (purple/green/yellow)
//   - Pace trace — dragging pointer showing where on this lap we are
//   - Stint projection — tire-life model, projected pace for remaining laps

const { useState, useMemo } = React;
const { LAPS, META, CORNER_COLORS } = F1Data;

function fmtLapTime(t) {
  if (!isFinite(t)) return "—:—.—";
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${s.toFixed(3).padStart(6, "0")}`;
}
function fmtDelta(d) {
  if (d == null) return "—";
  const sign = d > 0 ? "+" : d < 0 ? "–" : "±";
  return `${sign}${Math.abs(d).toFixed(3)}`;
}

function LapPanel({ lap, lapIdx, lapNumber, lapFrac, revealedLaps, mode }) {
  // --- Derived numbers ---
  const lapTime = lap.lap_time.mean;
  const pbLap = useMemo(() => {
    let best = null;
    for (const l of revealedLaps) {
      if (!best || l.lap_time.mean < best.lap_time.mean) best = l;
    }
    return best || lap;
  }, [revealedLaps, lap]);
  const pb = pbLap.lap_time.mean;
  const deltaPb = lapTime - pb;

  // Model prediction: a smoothed projection excluding noise (deterministic from lapIdx)
  const modelTime = 93.85 + (-0.035 * (21 - lapIdx)) + 0.018 * lapIdx + 0.0008 * lapIdx * lapIdx;
  const deltaModel = lapTime - modelTime;

  // Sector split — roughly 30/38/32 of lap time with per-lap variance via data hash
  const sectors = splitSectors(lap);
  const prevSectors = lapIdx > 0 ? splitSectors(LAPS[lapIdx - 1]) : null;
  const bestSectors = useMemo(() => {
    const b = [Infinity, Infinity, Infinity];
    for (const l of revealedLaps) {
      const s = splitSectors(l);
      for (let i = 0; i < 3; i++) if (s[i] < b[i]) b[i] = s[i];
    }
    return b;
  }, [revealedLaps]);

  return (
    <div style={{
      height: "100%", display: "grid", gridTemplateRows: "38px auto auto 1fr auto",
      minHeight: 0,
    }}>
      <LapHeader lapNumber={lapNumber} mode={mode}/>

      {/* Big lap time block */}
      <BigLapTime
        lapTime={lapTime}
        deltaPb={deltaPb}
        deltaModel={deltaModel}
        lapFrac={lapFrac}
        lapNumber={lapNumber}
      />

      {/* Sector bars */}
      <SectorBars sectors={sectors} best={bestSectors} prev={prevSectors} lapFrac={lapFrac}/>

      {/* Pace trace — history of lap times */}
      <PaceTrace revealedLaps={revealedLaps} lapIdx={lapIdx} />

      {/* Stint projection */}
      <StintProjection revealedLaps={revealedLaps} lapIdx={lapIdx} />
    </div>
  );
}

function LapHeader({ lapNumber, mode }) {
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
      <span style={{ color: "var(--text)", fontWeight: 700 }}>LAP</span>
      <span style={{ color: "var(--text-muted)" }}>·</span>
      <span>TIMING · DELTA · SECTORS · STINT MODEL</span>
      <span style={{ flex: 1 }}/>
      <span>{mode === "live" ? "LIVE FEED" : "REPLAY"}</span>
    </div>
  );
}

function BigLapTime({ lapTime, deltaPb, deltaModel, lapFrac, lapNumber }) {
  // Fake "in-progress" time when we're mid-lap: interpolate the final lap time by lapFrac.
  const elapsed = lapTime * lapFrac;
  const pbColor = deltaPb <= 0 ? "var(--purple)" : deltaPb < 0.1 ? "var(--ok)" : "var(--warn)";
  const modelColor = deltaModel < -0.05 ? "var(--ok)" : deltaModel > 0.1 ? "var(--hot)" : "var(--text-dim)";

  return (
    <div style={{
      padding: "16px 18px 12px",
      borderBottom: "1px solid var(--rule)",
    }}>
      <div style={{
        fontFamily: "var(--mono)", fontSize: 9, letterSpacing: 2,
        color: "var(--text-muted)", marginBottom: 6,
      }}>
        LAP {String(lapNumber).padStart(2, "0")} · IN PROGRESS
      </div>

      <div style={{
        fontFamily: "var(--mono)",
        fontSize: 56,
        fontWeight: 300,
        lineHeight: 1,
        color: "var(--text)",
        letterSpacing: 1,
        textShadow: "0 0 24px rgba(0,229,255,0.25)",
        display: "flex", alignItems: "baseline", gap: 8,
      }}>
        <span>{fmtLapTime(elapsed)}</span>
        <span style={{ fontSize: 14, color: "var(--text-muted)", letterSpacing: 3 }}>
          / {fmtLapTime(lapTime)}
        </span>
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12,
        marginTop: 12, fontFamily: "var(--mono)",
      }}>
        <DeltaBlock label="Δ PB"    value={fmtDelta(deltaPb)}    unit="s" color={pbColor}/>
        <DeltaBlock label="Δ MODEL" value={fmtDelta(deltaModel)} unit="s" color={modelColor}/>
      </div>
    </div>
  );
}

function DeltaBlock({ label, value, unit, color }) {
  return (
    <div style={{
      padding: "8px 10px",
      background: "var(--panel)",
      border: "1px solid var(--rule)",
      borderLeft: `2px solid ${color}`,
    }}>
      <div style={{ fontSize: 9, letterSpacing: 2, color: "var(--text-muted)" }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 500, color, marginTop: 2, letterSpacing: 0.5 }}>
        {value}<span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 3 }}>{unit}</span>
      </div>
    </div>
  );
}

// ── Sector bars ────────────────────────────────────────────────────────
function splitSectors(lap) {
  const t = lap.lap_time.mean;
  // deterministic split via lap number hash
  const h = (lap.lap_number * 9301 + 49297) % 100 / 100;
  const s1 = t * (0.30 + h * 0.02);
  const s2 = t * (0.38 + (1-h) * 0.02);
  const s3 = t - s1 - s2;
  return [s1, s2, s3];
}

function SectorBars({ sectors, best, prev, lapFrac }) {
  // Determine active sector from lapFrac
  const total = sectors.reduce((a,b) => a+b, 0);
  const bounds = [sectors[0], sectors[0] + sectors[1], total];
  const active = lapFrac * total < bounds[0] ? 0
    : lapFrac * total < bounds[1] ? 1 : 2;

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 2,
      padding: "12px 18px",
      borderBottom: "1px solid var(--rule)",
    }}>
      {sectors.map((s, i) => {
        const isBest = s <= best[i] + 0.001;
        const beatPrev = prev && s < prev[i];
        const isActive = i === active;
        // Color rules: purple = overall best, green = personal best sector / beat prev, yellow = slower
        const color = isBest ? "var(--purple)" : beatPrev ? "var(--ok)" : "var(--warn)";
        return (
          <div key={i} style={{
            padding: "8px 10px",
            background: "var(--panel)",
            borderLeft: `3px solid ${color}`,
            opacity: isActive ? 1 : 0.75,
            position: "relative",
            fontFamily: "var(--mono)",
          }}>
            {isActive && (
              <div style={{
                position: "absolute", top: 0, left: 0, right: 0, height: 2,
                background: "var(--accent)",
                boxShadow: "0 0 6px rgba(0,229,255,0.8)",
              }}/>
            )}
            <div style={{
              fontSize: 8.5, letterSpacing: 2, color: "var(--text-muted)",
              display: "flex", justifyContent: "space-between",
            }}>
              <span>S{i+1}</span>
              {isActive && <span style={{ color: "var(--accent)" }}>· LIVE</span>}
            </div>
            <div style={{ fontSize: 16, color: "var(--text)", marginTop: 2, fontWeight: 600, letterSpacing: 0.5 }}>
              {s.toFixed(3)}<span style={{ fontSize: 9, color: "var(--text-muted)", marginLeft: 2 }}>s</span>
            </div>
            <div style={{ fontSize: 8.5, letterSpacing: 1, color, marginTop: 2, fontWeight: 600 }}>
              {isBest ? "OVERALL BEST" : beatPrev ? "PERSONAL BEST" : "—"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Pace trace ─────────────────────────────────────────────────────────
function PaceTrace({ revealedLaps, lapIdx }) {
  // Tiny chart showing lap times over the stint revealed so far.
  const w = 420, h = 120, pad = { l: 34, r: 10, t: 20, b: 20 };
  const times = revealedLaps.map(l => l.lap_time.mean);
  if (times.length === 0) return null;
  const min = Math.min(...times) - 0.15;
  const max = Math.max(...times) + 0.15;
  const sx = (i) => pad.l + (i / Math.max(1, LAPS.length - 1)) * (w - pad.l - pad.r);
  const sy = (v) => pad.t + (1 - (v - min) / (max - min)) * (h - pad.t - pad.b);
  const pathD = revealedLaps.map((l, i) => `${i === 0 ? "M" : "L"}${sx(i).toFixed(1)} ${sy(l.lap_time.mean).toFixed(1)}`).join(" ");

  // Best lap idx
  let bestI = 0;
  for (let i = 1; i < revealedLaps.length; i++) {
    if (revealedLaps[i].lap_time.mean < revealedLaps[bestI].lap_time.mean) bestI = i;
  }

  return (
    <div style={{
      padding: "10px 18px 4px",
      borderBottom: "1px solid var(--rule)",
      display: "grid", gridTemplateRows: "auto 1fr",
      minHeight: 0,
    }}>
      <div style={{
        fontFamily: "var(--mono)", fontSize: 9, letterSpacing: 2,
        color: "var(--text-muted)",
        display: "flex", justifyContent: "space-between",
      }}>
        <span>PACE · STINT</span>
        <span>Δ {(max - min).toFixed(2)}s</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet"
        style={{ width: "100%", height: "100%", maxHeight: 130, marginTop: 6 }}>
        {/* baseline grid */}
        {[0.25, 0.5, 0.75].map((p, i) => (
          <line key={i}
            x1={pad.l} y1={pad.t + (h - pad.t - pad.b) * p}
            x2={w - pad.r} y2={pad.t + (h - pad.t - pad.b) * p}
            stroke="var(--rule)" strokeWidth="0.5" opacity="0.6"/>
        ))}
        {/* y axis labels */}
        <text x={pad.l - 4} y={pad.t + 4} fill="var(--text-muted)" fontFamily="var(--mono)"
          fontSize="8" textAnchor="end">{max.toFixed(1)}</text>
        <text x={pad.l - 4} y={h - pad.b + 3} fill="var(--text-muted)" fontFamily="var(--mono)"
          fontSize="8" textAnchor="end">{min.toFixed(1)}</text>
        <text x={pad.l - 4} y={h / 2 + 2} fill="var(--text-muted)" fontFamily="var(--mono)"
          fontSize="8" textAnchor="end" letterSpacing="1">s</text>
        {/* area under */}
        <path d={`${pathD} L${sx(revealedLaps.length-1).toFixed(1)} ${h - pad.b} L${sx(0).toFixed(1)} ${h - pad.b} Z`}
          fill="var(--accent)" opacity="0.1"/>
        <path d={pathD} fill="none" stroke="var(--accent)" strokeWidth="1.6" strokeLinejoin="round"/>
        {revealedLaps.map((l, i) => (
          <circle key={i} cx={sx(i)} cy={sy(l.lap_time.mean)} r={i === bestI ? 3 : 1.6}
            fill={i === bestI ? "var(--purple)" : "var(--accent)"}
            stroke={i === bestI ? "var(--panel-bg)" : "none"} strokeWidth="1.5"/>
        ))}
        {/* current lap marker */}
        <line x1={sx(lapIdx)} y1={pad.t} x2={sx(lapIdx)} y2={h - pad.b}
          stroke="var(--accent)" strokeWidth="0.8" strokeDasharray="3 3" opacity="0.6"/>

        {/* x axis every 5 laps */}
        {LAPS.filter(l => l.lap_number % 5 === 0 || l.lap_number === 1 || l.lap_number === LAPS.length)
          .map(l => (
            <text key={l.lap_number} x={sx(l.lap_number - 1)} y={h - 4}
              fill="var(--text-muted)" fontFamily="var(--mono)" fontSize="8"
              textAnchor="middle">L{l.lap_number}</text>
          ))}
      </svg>
    </div>
  );
}

// ── Stint projection ───────────────────────────────────────────────────
function StintProjection({ revealedLaps, lapIdx }) {
  // Use the last 3 revealed laps to fit a simple linear pace trend and project forward.
  // Also project avg tire wear across 4 corners.
  if (revealedLaps.length < 1) return null;

  const remaining = LAPS.length - (lapIdx + 1);
  const lastN = Math.min(5, revealedLaps.length);
  const tail = revealedLaps.slice(-lastN);
  const avgRecent = tail.reduce((a,l) => a + l.lap_time.mean, 0) / lastN;
  // slope: time per lap of degradation
  const slope = lastN > 1
    ? (tail[lastN-1].lap_time.mean - tail[0].lap_time.mean) / (lastN - 1)
    : 0.03;
  const projTimeNextLap = avgRecent + slope;
  const projTimeEndStint = avgRecent + slope * remaining;

  // wear projection: take avg of 4 corners
  const corners = ["fl","fr","rl","rr"];
  const lastLap = revealedLaps[revealedLaps.length - 1];
  const avgWear = corners.reduce((a,c) => a + lastLap[`e_tire_${c}`].mean, 0) / 4;
  const wearPct = Math.min(100, (avgWear / 22) * 100);
  // estimate laps to cliff (wear > 18 MJ)
  const wearSlope = revealedLaps.length > 1
    ? (lastLap.e_tire_fl.mean - revealedLaps[revealedLaps.length - 2].e_tire_fl.mean)
    : 0.9;
  const lapsToCliff = Math.max(0, Math.floor((18 - avgWear) / Math.max(0.1, wearSlope)));

  return (
    <div style={{
      padding: "10px 18px 14px",
      background: "var(--panel-header)",
      fontFamily: "var(--mono)",
    }}>
      <div style={{ fontSize: 9, letterSpacing: 2, color: "var(--text-muted)", marginBottom: 8 }}>
        STINT MODEL · PROJECTION
      </div>
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 6,
      }}>
        <ProjStat label="NEXT LAP" value={fmtLapTime(projTimeNextLap)} hint={`${slope >= 0 ? "+" : ""}${slope.toFixed(3)}s/lap`} hintColor={slope > 0.05 ? "var(--warn)" : "var(--text-muted)"}/>
        <ProjStat label="STINT END" value={fmtLapTime(projTimeEndStint)} hint={`${remaining} laps left`}/>
      </div>
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8,
      }}>
        <ProjStat label="AVG WEAR" value={`${wearPct.toFixed(0)}%`} hint={`${avgWear.toFixed(1)} MJ`}
          valueColor={wearPct > 75 ? "var(--hot)" : wearPct > 55 ? "var(--warn)" : "var(--text)"}/>
        <ProjStat label="CLIFF IN" value={lapsToCliff > 99 ? "—" : `${lapsToCliff}`}
          hint={lapsToCliff > 99 ? "well within window" : "laps (model)"}
          valueColor={lapsToCliff < 3 ? "var(--hot)" : lapsToCliff < 6 ? "var(--warn)" : "var(--ok)"}/>
      </div>
    </div>
  );
}

function ProjStat({ label, value, hint, valueColor = "var(--text)", hintColor = "var(--text-muted)" }) {
  return (
    <div style={{
      padding: "7px 9px",
      background: "var(--panel)",
      border: "1px solid var(--rule)",
    }}>
      <div style={{ fontSize: 8.5, letterSpacing: 2, color: "var(--text-muted)" }}>{label}</div>
      <div style={{ fontSize: 15, color: valueColor, marginTop: 2, fontWeight: 600, letterSpacing: 0.5 }}>{value}</div>
      <div style={{ fontSize: 8.5, color: hintColor, marginTop: 2, letterSpacing: 1 }}>{hint}</div>
    </div>
  );
}

window.CockpitLap = { Panel: LapPanel };
