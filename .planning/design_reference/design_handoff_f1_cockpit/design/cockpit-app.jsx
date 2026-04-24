/* global React, ReactDOM, F1Data, CockpitCar, CockpitLap, CockpitMap, CockpitPhysics */
// Cockpit app shell — top strip + 4-quadrant layout
// Layout (napkin):
//   ┌────────────────────────────────────────────────────────────────┐
//   │  TOP STRIP · session identity · scrubber · lap counter         │
//   ├───────────────────┬───────────────────┬────────────────────────┤
//   │                   │                   │  MAP (viewer dot)      │
//   │   CAR (top-down   │   LAP INFO        ├────────────────────────┤
//   │   integrated tire)│   time/sectors/   │  PHYSICS (tabbed)      │
//   │                   │   delta/pace/proj │                        │
//   └───────────────────┴───────────────────┴────────────────────────┘

const { useState, useEffect, useRef, useMemo, useCallback } = React;
const { META, LAPS } = F1Data;

const MAX_LAP = LAPS.length;

// -------- Simulated live/replay clock -----------------------------------
// Each lap runs ~94s. For the UI we speed it up: 1 lap = 4 real seconds at 1x.
const LAP_SECONDS = 4.0;

function App() {
  // mode: "live" (advances automatically) | "replay" (manual scrub)
  const [mode, setMode] = useState("live");
  const [speed, setSpeed] = useState(1);      // 1x, 2x, 4x, 8x
  const [playing, setPlaying] = useState(true);
  // continuous position through the stint, in laps as a float (1.000 … N.999)
  const [pos, setPos] = useState(1.0);
  const [hoveredCorner, setHoveredCorner] = useState(null);  // "fl"|"fr"|"rl"|"rr"|null
  const [hoveredTurn, setHoveredTurn] = useState(null);      // 0..1 fraction around lap, or null

  // Tick
  useEffect(() => {
    if (!playing) return;
    let raf, last = performance.now();
    const step = (t) => {
      const dt = (t - last) / 1000;
      last = t;
      setPos(p => {
        const next = p + (dt * speed) / LAP_SECONDS;
        if (next >= MAX_LAP + 0.999) {
          // loop in replay, stop in live
          if (mode === "replay") return 1.0;
          setPlaying(false);
          return MAX_LAP + 0.999;
        }
        return next;
      });
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, mode]);

  const lapIdx = Math.min(MAX_LAP - 1, Math.max(0, Math.floor(pos - 1)));
  const lapFrac = Math.max(0, Math.min(0.9999, pos - Math.floor(pos)));  // 0..1 within current lap
  const lap = LAPS[lapIdx];
  const lapNumber = lapIdx + 1;

  // revealed data depends on mode
  //   live: everything up to currentLap (the pending one is in-progress, not yet in CI)
  //   replay: everything in the stint is "available" but user is scrubbing history
  const revealedLaps = useMemo(() => {
    return LAPS.slice(0, lapNumber);
  }, [lapNumber]);

  function onModeChange(m) {
    setMode(m);
    if (m === "replay") {
      setPlaying(false);
    } else {
      setPos(p => (p < MAX_LAP ? p : 1.0));
      setPlaying(true);
    }
  }

  function seek(newPos) {
    setPos(Math.max(1.0, Math.min(MAX_LAP + 0.999, newPos)));
  }

  return (
    <div style={{
      minHeight: "100vh",
      display: "grid",
      gridTemplateRows: "52px 1fr",
      background: "var(--bg)",
    }}>
      <TopStrip
        mode={mode}
        onModeChange={onModeChange}
        playing={playing}
        onPlayToggle={() => setPlaying(p => !p)}
        speed={speed}
        onSpeedChange={setSpeed}
        pos={pos}
        onSeek={seek}
      />

      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(460px, 33%) minmax(420px, 32%) minmax(480px, 35%)",
        gridTemplateRows: "minmax(400px, 55%) minmax(320px, 45%)",
        gap: 1,
        background: "var(--rule)",
        padding: 1,
      }}>
        {/* Left column spans both rows */}
        <div style={{ gridColumn: 1, gridRow: "1 / span 2", background: "var(--panel-bg)" }}>
          <CockpitCar.Panel
            lap={lap}
            lapNumber={lapNumber}
            lapFrac={lapFrac}
            hoveredCorner={hoveredCorner}
            setHoveredCorner={setHoveredCorner}
          />
        </div>

        {/* Middle column spans both rows */}
        <div style={{ gridColumn: 2, gridRow: "1 / span 2", background: "var(--panel-bg)" }}>
          <CockpitLap.Panel
            lap={lap}
            lapIdx={lapIdx}
            lapNumber={lapNumber}
            lapFrac={lapFrac}
            revealedLaps={revealedLaps}
            mode={mode}
          />
        </div>

        {/* Right top: map */}
        <div style={{ gridColumn: 3, gridRow: 1, background: "var(--panel-bg)" }}>
          <CockpitMap.Panel
            lap={lap}
            lapNumber={lapNumber}
            lapFrac={lapFrac}
            hoveredTurn={hoveredTurn}
            setHoveredTurn={setHoveredTurn}
          />
        </div>

        {/* Right bottom: physics */}
        <div style={{ gridColumn: 3, gridRow: 2, background: "var(--panel-bg)" }}>
          <CockpitPhysics.Panel
            revealedLaps={revealedLaps}
            lapNumber={lapNumber}
            hoveredCorner={hoveredCorner}
            setHoveredCorner={setHoveredCorner}
          />
        </div>
      </div>
    </div>
  );
}

// ---------- Top Strip ----------------------------------------------------
function TopStrip({ mode, onModeChange, playing, onPlayToggle, speed, onSpeedChange, pos, onSeek }) {
  const lapNumber = Math.min(MAX_LAP, Math.floor(pos));
  const lapFrac = pos - Math.floor(pos);

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "auto 1fr auto",
      alignItems: "center",
      gap: 0,
      padding: "0 16px",
      background: "var(--panel-header)",
      borderBottom: "1px solid var(--rule-strong)",
      fontFamily: "var(--mono)",
      fontSize: 11,
      color: "var(--text-dim)",
      letterSpacing: 1.2,
      height: 52,
    }}>
      {/* Left block: session identity */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{
          width: 4, height: 22, background: META.driver.teamColor,
        }}/>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ color: "var(--text)", fontSize: 13, fontWeight: 700, letterSpacing: 2.2 }}>
              {META.driver.code}
            </span>
            <span style={{ color: "var(--text-dim)", fontSize: 10.5, letterSpacing: 1.6 }}>
              · {META.driver.team.toUpperCase()}
            </span>
          </div>
          <div style={{ fontSize: 9.5, letterSpacing: 1.6, color: "var(--text-dim)" }}>
            R{String(META.race.round).padStart(2, "0")} · {META.race.name.toUpperCase()} · STINT {META.stint.id}
            <span style={{ color: "var(--compound-medium, #FFD500)", fontWeight: 700, marginLeft: 6 }}>
              {META.stint.compound}
            </span>
          </div>
        </div>

        <Divider/>

        {/* Mode toggle */}
        <div style={{ display: "flex", border: "1px solid var(--rule-strong)", overflow: "hidden" }}>
          {["live", "replay"].map(m => (
            <button key={m} onClick={() => onModeChange(m)}
              style={{
                padding: "6px 12px",
                background: mode === m ? "var(--accent)" : "transparent",
                border: "none",
                color: mode === m ? "#000" : "var(--text-dim)",
                fontSize: 10, fontWeight: 700, letterSpacing: 2,
              }}>
              {m === "live" && <span style={{
                display: "inline-block", width: 6, height: 6, borderRadius: "50%",
                background: mode === "live" ? "#000" : "var(--hot)",
                marginRight: 6, verticalAlign: "middle",
                animation: mode === "live" ? "none" : "blink-red 1.6s infinite",
              }}/>}
              {m.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Middle block: scrubber */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 20px" }}>
        <button onClick={onPlayToggle} style={{
          background: "transparent", border: "1px solid var(--rule-strong)",
          color: "var(--text)", padding: "4px 10px", fontSize: 10, letterSpacing: 1.5, fontWeight: 700,
        }}>
          {playing ? "❚❚  PAUSE" : "►  PLAY"}
        </button>

        <div style={{ flex: 1, position: "relative" }}>
          <Scrubber pos={pos} onSeek={onSeek}/>
        </div>

        <div style={{ display: "flex", gap: 0, border: "1px solid var(--rule-strong)" }}>
          {[1, 2, 4, 8].map(s => (
            <button key={s} onClick={() => onSpeedChange(s)}
              style={{
                padding: "4px 8px",
                background: speed === s ? "var(--rule-strong)" : "transparent",
                border: "none",
                color: speed === s ? "var(--text)" : "var(--text-dim)",
                fontSize: 10, fontWeight: 600, minWidth: 28,
              }}>
              {s}×
            </button>
          ))}
        </div>
      </div>

      {/* Right block: lap counter */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ fontSize: 9, color: "var(--text-muted)", letterSpacing: 2 }}>LAP</div>
        <div style={{ color: "var(--text)", fontSize: 22, fontWeight: 700, fontFamily: "var(--mono)", letterSpacing: 1 }}>
          {String(lapNumber).padStart(2, "0")}
          <span style={{ color: "var(--text-muted)", fontSize: 14, fontWeight: 400 }}> / {MAX_LAP}</span>
        </div>
        <div style={{
          fontSize: 9, color: "var(--text-dim)", letterSpacing: 1.5,
          padding: "3px 6px", border: "1px solid var(--rule)",
        }}>
          {(lapFrac * 100).toFixed(0).padStart(2, "0")}% THRU
        </div>
      </div>
    </div>
  );
}

function Divider() {
  return <div style={{ width: 1, height: 24, background: "var(--rule-strong)" }}/>;
}

function Scrubber({ pos, onSeek }) {
  const ref = useRef(null);
  const [dragging, setDragging] = useState(false);

  const frac = (pos - 1) / (MAX_LAP - 1);

  const onPointer = useCallback((e) => {
    const r = ref.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    onSeek(1 + x * (MAX_LAP - 1));
  }, [onSeek]);

  useEffect(() => {
    if (!dragging) return;
    const mv = (e) => onPointer(e);
    const up = () => setDragging(false);
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
    };
  }, [dragging, onPointer]);

  return (
    <div ref={ref}
      onPointerDown={(e) => { setDragging(true); onPointer(e); }}
      style={{
        height: 24, position: "relative", cursor: "pointer",
        display: "flex", alignItems: "center",
      }}>
      {/* Track */}
      <div style={{
        position: "absolute", left: 0, right: 0, top: 10, height: 3,
        background: "var(--rule-strong)",
      }}/>
      {/* Progress */}
      <div style={{
        position: "absolute", left: 0, top: 10, height: 3,
        width: `${frac * 100}%`,
        background: "var(--accent)",
      }}/>
      {/* Tick marks per lap */}
      {Array.from({ length: MAX_LAP }).map((_, i) => (
        <div key={i} style={{
          position: "absolute",
          left: `${(i / (MAX_LAP - 1)) * 100}%`,
          top: 7, width: 1, height: 9,
          background: "var(--rule-strong)",
          transform: "translateX(-0.5px)",
        }}/>
      ))}
      {/* Handle */}
      <div style={{
        position: "absolute",
        left: `${frac * 100}%`,
        top: 4, width: 3, height: 16,
        background: "var(--accent)",
        transform: "translateX(-50%)",
        boxShadow: "0 0 8px rgba(0,229,255,0.7)",
      }}/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);

window.Cockpit = { App };
