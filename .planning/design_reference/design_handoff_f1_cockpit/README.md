# Handoff: F1 Pit-Wall Cockpit

## Screenshots

Reference captures in `screenshots/`:

- `01-cockpit-overview.png` — mid-stint (lap 20), **GRIP μ** tab active
- `02-early-stint-tread.png` — early stint (lap 4), **TREAD TEMP °C** tab active (default)
- `03-late-stint-wear.png` — late stint (lap 20), **WEAR E MJ** tab active, visible wear erosion on rear tires

## Overview

A single-screen telemetry dashboard for a Formula 1 race engineer ("pit-wall cockpit"). Displays live or replayable physics-model output for one driver, one stint: per-corner tire temperatures, grip, wear and slip on a top-down car schematic; lap timing with sectors and stint projection; a track map with the car's live position; and a tabbed physics chart showing lap-by-lap evolution of the four cornerwise metrics with 95% confidence bands.

The aesthetic is deliberately **engineering-first** (Mercedes/Red Bull pit-wall), not broadcast TV: dark blue-black panels, thin rules, data painted directly on geometry, monospace numerics with tabular figures. No emoji, no gradients, no rounded corners.

## About the Design Files

The files in `design/` are **design references created in HTML/React + inline Babel** — prototypes that show intended look, interaction, and data shape. They are not production code to copy directly.

Your task is to **recreate these designs in the target codebase's existing environment** (likely a real React + build-tool setup, or whatever the app is using) using its established patterns: its routing, state management, styling system, component primitives, and data-fetching layer. If no frontend environment exists yet, a modern React + Vite + CSS-modules (or Tailwind) stack is a sensible default — the current design is pure React functional components with inline-style objects, so porting is mostly mechanical.

## Fidelity

**High-fidelity.** Pixel-perfect mockups with final colors, typography, spacing, and interactions. Every token in the "Design Tokens" section below is the exact value to use. The chassis SVG, the track SVG, the physics-chart layout, the tire geometry — all are production-ready dimensions.

---

## Layout

Single full-viewport page at minimum width **1600px** (horizontal scroll below that). Structure:

```
┌──────────────────────────────────────────────────────────────────────┐
│  TOP STRIP — session identity · mode toggle · scrubber · lap counter │   52px
├──────────────────┬───────────────────┬───────────────────────────────┤
│                  │                   │  MAP (Bahrain + car dot)      │  ~55%
│   CAR            │   LAP INFO        │                               │
│   (top-down      │   big lap time /  ├───────────────────────────────┤
│   schematic w/   │   sectors / pace  │                               │
│   integrated     │   trace / stint   │  PHYSICS                      │  ~45%
│   telemetry)     │   projection      │  (tabbed 4-chart)             │
│                  │                   │                               │
└──────────────────┴───────────────────┴───────────────────────────────┘
    33%                32%                    35%
```

- Outer grid: `grid-template-rows: 52px 1fr`; main area is a 3-column × 2-row CSS grid with **1px gutters on a `var(--rule)` background** (so the gutters read as thin rules).
- **Car** panel spans both rows of column 1; **Lap Info** spans both rows of column 2; **Map** is column 3 row 1; **Physics** is column 3 row 2.
- Panels: `background: var(--panel-bg)` with a 38px header strip inside each (`background: var(--panel-header)`, bottom rule, left 2px accent tick).

---

## Screens / Views

This is a **single screen**. Sections below describe each panel.

### 1. Top Strip

**Purpose:** Session identity (who/where), playback mode, scrubber, lap counter.

**Layout:** `grid-template-columns: auto 1fr auto`, 52px tall, 16px horizontal padding, `background: var(--panel-header)`, bottom border `1px solid var(--rule-strong)`. Font: JetBrains Mono 11px, letter-spacing 1.2, `color: var(--text-dim)`.

**Left block** (session identity):
- 4×22px vertical tick in driver's team color (Ferrari red `#DC0000` for LEC).
- Two-line label:
  - Line 1: `LEC` (13px, weight 700, letter-spacing 2.2, color `var(--text)`) · `FERRARI` (10.5px, dim, letter-spacing 1.6).
  - Line 2: `R01 · BAHRAIN GRAND PRIX · STINT 1` (9.5px, letter-spacing 1.6, dim) followed by `MEDIUM` (bold, colored `#FFD500`).
- Vertical 1×24px divider (`var(--rule-strong)`).
- **Mode toggle** — two segmented buttons: `LIVE` | `REPLAY`. Active = `var(--accent)` background, black text, 700 weight, letter-spacing 2. Inactive = transparent, dim text. LIVE button shows a 6×6px red dot (`var(--hot)`) pulsing at 1.6s (keyframe `blink-red`) — solid black when active.

**Middle block** (scrubber):
- **Play/Pause button:** `[ ❚❚ PAUSE ]` / `[ ► PLAY ]`, transparent background, 1px `var(--rule-strong)` border, 4×10px padding, 10px text, letter-spacing 1.5, weight 700.
- **Scrubber track** (flex:1):
  - 3px rail, background `var(--rule-strong)`, at y=10 of 24px height.
  - Progress fill from left: `width: pct%`, `background: var(--accent)`.
  - Per-lap tick marks: 1×9px verticals every `100 / (MAX_LAP-1)` %.
  - Handle: 3×16px bar at current position, `background: var(--accent)`, `box-shadow: 0 0 8px rgba(0,229,255,0.7)`.
  - Entire bar is click-to-seek and pointer-drag.
- **Speed toggle** — four segmented buttons `1× 2× 4× 8×`, one border wrapping all. Active = `var(--rule-strong)` background, `var(--text)`. Inactive = transparent, dim.

**Right block** (lap counter):
- `LAP` label (9px, muted, letter-spacing 2).
- Big number: `01` (22px, weight 700, mono, letter-spacing 1) with ` / 22` suffix (14px, muted, weight 400).
- Percent-through badge: `44% THRU` — 9px, dim, letter-spacing 1.5, 3×6px padding, 1px `var(--rule)` border.

### 2. Car Panel (column 1, full height)

**Purpose:** Top-down F1 chassis schematic with per-corner telemetry painted on the geometry. Hovering any wheel or footer readout highlights both.

**Grid rows:** `38px header / 1fr SVG / auto footer`.

**Header:** `[accent tick] CAR · SF-24 · TOP-DOWN · INTEGRATED TELEMETRY ... LAP 01`.

**SVG canvas** (viewBox 400×780, nose up, `preserveAspectRatio="xMidYMid meet"`):
- Background: `radial-gradient(ellipse at center, #0a1018 0%, var(--panel-bg) 70%)`.
- 20px tech-grid pattern (`<pattern id="tech-grid">`) — faint `var(--rule)` lines.
- Centerline: dashed `var(--rule-strong)` vertical.
- Axle reference lines: horizontal dashed across both axles, labeled `FRONT AXLE` / `REAR AXLE` (7px mono, muted, letter-spacing 1.2).
- **Compound strip:** 120×3px bar at y≈18 (center), compound color (e.g. `#FFD700` for MEDIUM), label below: `MEDIUM · AGE 3` (8px, dim).
- **Chassis outline** (see `cockpit-car.jsx::CarChassis`): front wing with endplates, nose cone, front suspension arms, main tub, halo (ellipse), cockpit (dark ellipse), sidepods, airbox, engine/gearbox area with horizontal rib lines, floor (dashed), rear suspension, rear wing with DRS line, diffuser hints. All `fill: var(--panel)` or none, stroke `var(--rule-strong)` with 1.1px weight, round joins/caps.
- **Direction arrow** at top: cyan accent arrow + label `DIR`.
- **Dimension annotations:** wheelbase marker on right (`WB 3600`), track marker between front tires (`TRACK 2000`), 7px muted mono.

**Tire geometry:**
| Corner | cx | cy | w | h |
|---|---|---|---|---|
| FL | 82  | 240 | 46 | 78  |
| FR | 318 | 240 | 46 | 78  |
| RL | 76  | 600 | 54 | 96  |
| RR | 324 | 600 | 54 | 96  |

**Each wheel renders (see `CarWheel`):**
- Brake glow behind tire: `<ellipse>` filled by `url(#brake-glow)` radial (amber→red→transparent), opacity scaled `0.25 + brakeNorm * 0.55` where `brakeNorm = (brakeT - 300) / 500`.
- Tire outer stroke: 1.5px inset rect, `var(--text-muted)` normally, `var(--accent)` + 1.4px when hovered.
- Tire fill: viridis-mapped temp color, opacity 0.88.
- Tread grooves: 7 horizontal black lines at `rgba(0,0,0,0.45)`, 0.8px — divides tire into 8 bands.
- **Wear erosion:** `round(wear * 8)` bands replaced with dark `rgba(10,14,21,0.78)` rectangles. Erosion leads from the **front** of the tire on front axle (leading edge) and **rear** of the tire on rear axle — physically correct.
- Temp number centered: black-transparent badge 32×18px, white 11/12px mono 700, `"103°"` format.
- Corner label (FL/FR/RL/RR): 11px mono 700, letter-spacing 2, placed on the **inboard** side of the tire.
- **Grip ladder** (outboard): 10 vertical segments stacked, 14px wide, `h/10` each, lit count = `round(gripNorm * 10)` where `gripNorm = (grip - 1.05) / 0.45`. Lit = `var(--accent)` with opacity ramp `0.4 + 0.6 * (seg/10)`. Unlit = `var(--rule-strong)` @ 0.5. `μ` label above, numeric below (`1.42`, 8px accent mono).
- **Wear bar** (horizontal under tire): background `var(--rule-strong)`, fill width = `w * wear`, color ramps: `<45%` green `#22E27A`, `45–70%` amber `#FFB020`, `>70%` red `#FF3344`. Label below: `WEAR 34%` 7px muted.
- **Slip angle tick** above tire: rotated line 14px with dot, rotation = `clamp(-6, 6, slip) * 2 * (isLeft ? -1 : 1)`. Label `α 3.2°` above.
- **Brake temp** inboard: `BR\n560°C` — 7px muted label, 9px amber `#FFB020` value.
- CI halo: 2px outset rect stroked with `tempColor`, stroke-width `0.6 + min(3, (tempHi-tempLo) * 0.12)`, opacity 0.35 — shows temperature uncertainty.
- Hover: dashed 3px `var(--accent)` rectangle encompassing the entire wheel region.

**Footer readouts:** 4-column grid, `background: var(--panel-header)`, 1px gaps. Each column:
- Corner abbreviation + axle label (e.g. `FL FRONT·L`).
- Rows: `T` (temp °C with CI range), `μ` (grip with ±), `WEAR` (% colored by threshold), `α` (slip °), `BRK` (brake °C, always amber).
- Active corner: `var(--panel-header-hi)` background + 2px left accent border. Hover syncs with SVG.

### 3. Lap Info Panel (column 2, full height)

**Purpose:** Current lap time, delta to PB/model, sector bars, pace trace, stint projection.

**Grid rows:** `38px header / auto big-time / auto sectors / 1fr pace trace / auto projection`.

**Header:** `[tick] LAP · TIMING · DELTA · SECTORS · STINT MODEL ... LIVE FEED` (or `REPLAY`).

**Big Lap Time block** (16×18 padding, bottom rule):
- Eyebrow: `LAP 01 · IN PROGRESS` — 9px muted mono letter-spacing 2.
- Main time: **56px mono weight 300**, `color: var(--text)`, `letter-spacing: 1`, `text-shadow: 0 0 24px rgba(0,229,255,0.25)`.
  - Format: `M:SS.SSS` (e.g. `1:33.851`). Shown as elapsed (interpolated by lapFrac) with ` / FINAL` suffix in 14px muted.
- Two delta blocks side by side (12px gap):
  - `Δ PB` — green `var(--ok)` if ≤0, purple `var(--purple)` if negative, warn `var(--warn)` if >0.1.
  - `Δ MODEL` — `var(--ok)` if <-0.05, `var(--hot)` if >0.1, dim otherwise.
  - Each: 1px `var(--rule)` border, **2px left border in color**, label 9px muted letter-spacing 2, value 20px weight 500 in delta color, unit `s` 11px muted.

**Sector bars:** 3-column grid (2px gap) of sector cards:
- Background `var(--panel)`, 3px left border in sector color.
- Colors: `var(--purple)` if overall best, `var(--ok)` if PB for this session, `var(--warn)` otherwise.
- Active sector (determined by lapFrac × total time vs boundaries): full opacity + 2px accent top bar with cyan glow; others at 0.75 opacity.
- Each card: `S1 · LIVE` header (8.5px, muted, letter-spacing 2), time `28.521s` 16px weight 600, status line `OVERALL BEST` / `PERSONAL BEST` / `—` 8.5px in sector color.

**Pace trace:** SVG line chart, viewBox 420×120, pad `{l:34, r:10, t:20, b:20}`:
- Y grid at 0.25, 0.5, 0.75 — thin `var(--rule)`.
- Area under curve: `var(--accent)` at 0.1 opacity.
- Line: `var(--accent)`, 1.6px, round joins.
- Points: 1.6px accent circles; best lap = 3px `var(--purple)` with 1.5px `var(--panel-bg)` stroke.
- Current lap: dashed vertical crosshair at `sx(lapIdx)`, accent 0.8px.
- Y labels: min/max floats at top/bottom; X labels every 5 laps + first + last.
- Header: `PACE · STINT` left, `Δ 0.42s` right (9px muted).

**Stint projection** (bottom, `background: var(--panel-header)`):
- Eyebrow: `STINT MODEL · PROJECTION` 9px muted letter-spacing 2.
- 2×2 grid of stat cards (8px gap), each card:
  - `var(--panel)` bg, 1px `var(--rule)` border, 7×9 padding.
  - `LABEL` (8.5px muted letter-spacing 2), `VALUE` (15px weight 600 letter-spacing 0.5), `HINT` (8.5px muted letter-spacing 1).
- Stats: `NEXT LAP` (projected), `STINT END` (projected), `AVG WEAR` (% — colored threshold), `CLIFF IN` (laps — green if >6, amber if 3–6, red if <3).

### 4. Map Panel (column 3, row 1)

**Purpose:** Bahrain circuit outline with the car's live position as a glowing dot.

**SVG viewBox 1×1** (normalized), `xMidYMid meet`, same radial-gradient background.
- 0.05-spacing grid pattern.
- Track rendered in three sector colors (shades of teal: `#3a98b4`, `#2a7a93`, `#1d6278`), 0.015 stroke, round caps/joins.
- Faint accent glow under track (0.028 stroke at 0.15 opacity).
- Dashed centerline (0.0015 stroke, 0.004/0.006 dash, 0.12 opacity).
- Sector boundary markers: small 0.008r `var(--warn)` dots with `S2`/`S3` labels above.
- Turn numbers: 0.006r muted dots + `T1`/`T4`/… labels, 0.7 opacity.
- Start/Finish: chequered 0.024×0.006 stripe pattern + white `S/F` label.
- **Car trail:** last 20% of lap, quadratic alpha fade, driver color (Ferrari red), 0.004 stroke, round caps.
- **Car dot:** 3 concentric circles with `dot-glow` filter — 0.014r team color @ 0.3, 0.008r team color solid, 0.004r white center. Plus a 0.025-long heading line in team color from center.
- Top-left info: `BAHRAIN · 5.412 km · 15T` (8.5px muted letter-spacing 1.5), line below `CW · START/FIN ↗`.
- Bottom-right HUD (8×10 padding, `rgba(7,10,17,0.82)` + 4px backdrop-blur, 1px `var(--rule)` border):
  - `LIVE · SECTOR N` eyebrow 8.5px muted letter-spacing 2.
  - Pseudo-speed (kph) — big 24px weight 600.
  - Two MiniBars: `THR` (green), `BRK` (red) — 3px rails.

### 5. Physics Panel (column 3, row 2)

**Purpose:** Lap-by-lap evolution of the four cornerwise physics metrics with 95% confidence bands. Tabbed.

**Grid rows:** `38px header / auto tab strip / 1fr charts`.

**Header:** `[tick] PHYSICS · LAP-BY-LAP · CI₉₅ ... 5/22 LAPS`.

**Tab strip:** 4 equal-flex buttons, letterspaced labels + unit:
- `TREAD TEMP °C` (accent `#FFD700`)
- `GRIP μ` (accent `#00E5FF`)
- `WEAR E MJ` (accent `#FFB020`)
- `SLIP α PEAK °` (accent `#A855F7`)

Active tab: `var(--panel-header-hi)` bg, 2px bottom border in tab accent color, text `var(--text)` 700. Inactive: transparent bg, dim text 500.

**Charts:** 4 stacked equal-height small-multiples, one per corner (FL, FR, RL, RR). Each chart:
- pad `{l:40, r:12, t:8, b:(isLast ? 18 : 6)}`.
- 4 horizontal grid lines (0, 1/3, 2/3, 1) at `var(--rule)` 0.4px 0.7 opacity.
- Vertical grid every 5 laps + lap 1 + last lap.
- **CI band:** filled polygon from hi→lo in corner color at 0.12 opacity.
- **Mean line:** 1.5px corner color, round joins, with 1.6r dots at each lap.
- Y axis: 3 ticks (min, mid, max) using domain-specific format (°C/float/MJ/°).
- Corner label badge top-left: 24×12 black-transparent bg, 0.6px colored border, 9px weight 700 letter-spacing 1 in corner color.
- **Hover crosshair:** vertical line in corner color at 0.7 opacity, 3r solid dot, tooltip card `L5  103.2  ±1.8` with corner border.
- Last chart also draws X-axis lap labels (L1, L5, L10, …, L22).
- Hover state: whole chart gets `var(--panel-header-hi)` bg and 2px left border in corner color.

**Corner colors (Okabe–Ito colorblind-safe):**
| Corner | Hex |
|---|---|
| FL | `#E69F00` (orange) |
| FR | `#56B4E9` (sky) |
| RL | `#009E73` (teal-green) |
| RR | `#F0E442` (yellow) |

---

## Interactions & Behavior

### Clock
- Constant `LAP_SECONDS = 4.0` — **one real lap compressed to 4 seconds at 1× speed** (prototype tempo; production should use the real ~90s lap or a configurable multiplier).
- `pos` is a float 1.000…MAX_LAP.999 representing continuous stint position.
- Tick via `requestAnimationFrame`: `pos += (dt * speed) / LAP_SECONDS`.
- At end of stint: **live** mode pauses and clamps; **replay** mode loops to 1.0.

### Mode toggle
- `live`: auto-plays, `replay` toggles to manual-only.
- Switching to `replay` pauses.
- Switching to `live` auto-plays and resets `pos` to 1.0 if we had run past the end.

### Scrubber
- `onPointerDown` → begin drag, seek immediately.
- Global `pointermove` during drag → continuous seek.
- Global `pointerup` → end drag.
- Seek clamped to `[1.0, MAX_LAP + 0.999]`.

### Hover sync
- Hovering any wheel in the Car SVG sets `hoveredCorner` in app state — this highlights the matching footer readout AND the matching physics chart (`2px left border + highlighted bg`).
- Hovering a footer readout or a physics chart also sets `hoveredCorner`, completing the two-way sync.

### Physics chart hover
- `onMouseMove` computes hovered lap from pixel X.
- Shows vertical crosshair, bold point marker, and floating tooltip card.
- Tooltip clamps to panel bounds.

### Data reveal model
- **`revealedLaps = LAPS.slice(0, lapNumber)`** — only laps completed up to and including the current lap are available for PB, pace-trace history, and projection.
- The in-progress lap's time is shown as elapsed (`lapTime * lapFrac`).

### Sector transitions
- Active sector derived from `lapFrac * totalLapTime` vs cumulative sector boundaries.
- As a sector becomes active it gets a 2px accent top bar with cyan glow.

---

## State Management

Single `App` functional component owns all state:

```js
const [mode, setMode]           = useState("live");       // "live" | "replay"
const [speed, setSpeed]         = useState(1);            // 1 | 2 | 4 | 8
const [playing, setPlaying]     = useState(true);
const [pos, setPos]             = useState(1.0);          // float 1..MAX_LAP+0.999
const [hoveredCorner, setHoveredCorner] = useState(null); // "fl"|"fr"|"rl"|"rr"|null
const [hoveredTurn, setHoveredTurn]     = useState(null); // 0..1 | null (reserved for turn highlight)
```

Derived (per render):
- `lapIdx = clamp(floor(pos - 1), 0, MAX_LAP-1)`
- `lapFrac = clamp(pos - floor(pos), 0, 0.9999)`
- `lap = LAPS[lapIdx]`
- `lapNumber = lapIdx + 1`
- `revealedLaps = LAPS.slice(0, lapNumber)` (memoized)

Port this to the target state manager (Redux slice / Zustand store / Context / etc) by mirroring these fields. **`pos` should be the single source of truth** — everything else derives from it + `mode`.

---

## Data Fetching

The prototype ships with a static fixture for Bahrain GP / LEC / Stint 1 in `design/data.jsx` — 22 laps of per-corner telemetry generated deterministically from a seeded hash.

**Schema per lap** (see `data.jsx::buildLaps`):

```ts
type CI = { mean: number; lo_95: number; hi_95: number };

type Lap = {
  lap_number: number;                // 1-indexed within stint
  stint_age: number;                 // laps on this set

  lap_time: CI;                      // seconds
  sliding_power_total: CI;           // kW total across 4 wheels

  // Per-corner (c ∈ {fl, fr, rl, rr}):
  [`t_tread_${c}`]: CI;              // tread surface °C
  [`grip_${c}`]: CI;                 // μ (tire grip coefficient)
  [`e_tire_${c}`]: CI;               // cumulative wear energy, MJ
  [`slip_angle_${c}`]: CI;           // peak slip angle, degrees
};
```

When wiring to a real backend:
- Replace `LAPS = buildLaps()` with a fetched array.
- Keep the CI triplet shape — the physics panel renders the band from `lo_95 ↔ hi_95` and the line from `mean`.
- `TRACK_POINTS` is a 260-point polyline in `[0,1]²` space for the circuit outline — fetch per-race from your track-geometry service.
- `SECTOR_BOUNDS`, `TURNS` are derived from the track geometry and sector timing.
- `META` (race/driver/stint) becomes response metadata.

The prototype has no loading/error states because it uses static data. The target implementation should add:
- Skeleton placeholders in each panel during first fetch.
- Error fallback panel for fetch failure.
- Empty state if no laps are yet available for the stint.

---

## Design Tokens

### Colors

```css
/* Backgrounds — engineering blacks */
--bg:             #05070b;   /* page */
--panel:          #0a0e15;   /* deep panel, chassis fill */
--panel-bg:       #070a11;   /* panel body */
--panel-header:   #0c1119;   /* panel header strip */
--panel-header-hi:#111827;   /* hovered/active panel header */

/* Rules */
--rule:           #1a2130;   /* thin divider */
--rule-strong:    #2a3445;   /* stronger divider, input borders */

/* Text */
--text:           #e8eef7;   /* primary */
--text-dim:       #6a7788;   /* secondary */
--text-muted:     #46525f;   /* labels, subtle metadata */

/* Accent + signal */
--accent:         #00E5FF;   /* cyan — primary UI accent */
--accent-dim:     #0092a8;
--hot:            #FF3344;   /* red — live indicator, critical */
--warn:           #FFB020;   /* amber — warning, brake temp */
--ok:             #22E27A;   /* green — ok / improving */
--purple:         #A855F7;   /* overall best marker */

/* Team */
--ferrari:        #DC0000;
```

### Domain-specific palettes

**Tire compounds (FIA):**
| Compound | Hex |
|---|---|
| SOFT | `#FF3333` |
| MEDIUM | `#FFD700` |
| HARD | `#FFFFFF` |
| INTER | `#22C55E` |
| WET | `#3B82F6` |

**Corner (Okabe–Ito, colorblind-safe):** see Physics section above.

**Viridis temperature scale** (tread temp 60–120°C): 9-stop gradient, see `data.jsx::VIRIDIS`. Use as `tempToViridis(°C)`.

### Typography

- Monospace: **JetBrains Mono** weights 300/400/500/600/700 (`var(--mono)`).
- Sans: **Inter** weights 300/400/500/600/700 (`var(--sans)`) — used only for body text fallback. Headings, numerics, labels are all JetBrains Mono.
- `font-feature-settings: "tnum" 1, "ss01" 1;` on `<body>` for tabular figures and stylistic alternate.

**Canonical sizes** (used across the design):

| Role | Size | Weight | Letter-spacing |
|---|---|---|---|
| Big lap time | 56px | 300 | 1 |
| Big number (speed, lap counter) | 22–24px | 600–700 | 0.5–1 |
| Stat value | 15–20px | 500–600 | 0.5 |
| Sector time | 16px | 600 | 0.5 |
| Section title / panel header | 10px | 700 | 2 |
| Metric tab label | 9.5px | 500/700 | 1.6 |
| Eyebrow / annotation | 8.5–9px | — | 1.5–2 |
| SVG axis tick | 7–8px | — | 1 |
| SVG small label | 7px | — | 1–1.2 |

### Spacing

- Panel padding: **14–18px horizontal, 8–16px vertical** (varies by density).
- Grid gap between cards: **2–12px** (inner grids) / **1px** (panel separators rendered as rules).
- Inline gap between label/value: **6–10px**.

### Rules

**No rounded corners anywhere.** All borders, badges, panels are hard 1px rectangles. Exception: the tire CI halo uses a 1px radius on its badge rect — optional.

### Shadows

Used sparingly:
- Scrubber handle: `box-shadow: 0 0 8px rgba(0,229,255,0.7);`
- Big lap time: `text-shadow: 0 0 24px rgba(0,229,255,0.25);`
- Car dot: SVG `<filter id="dot-glow">` with 0.004 gaussian blur + `feMerge`.
- Dropdown menu (if you port the selector): `box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,229,255,0.15);`.

### Animation

- `@keyframes blink-red`: 1.6s infinite, 50% opacity at midpoint — used on the LIVE indicator dot.
- `@keyframes pulse-dot`: 2s, box-shadow spreading from `rgba(0,229,255,0.55)` to transparent — reserved for data-arrival indicators.
- Easing: all interactive transitions use `140–180ms ease` (dropdown open, team-color bar swap).

---

## Assets

**None imported from disk.** Everything is inline SVG.

- Chassis outline: hand-drawn SVG paths in `cockpit-car.jsx::CarChassis` (~30 path/line/rect elements). Based on a generic 2024 F1 top-down silhouette (Ferrari SF-24 proportions: wheelbase 3600mm, track 2000mm).
- Track outline: Catmull-Rom smoothed polyline from ~43 hand-placed waypoints in `data.jsx::buildBahrainPath`. For other circuits, add more waypoint arrays keyed by `race.id`.
- Viridis color ramp: 9-stop RGB list in `data.jsx::VIRIDIS`.

**Fonts** loaded from Google Fonts:

```html
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
```

In the target app, self-host these via your build system's font pipeline — don't rely on the Google CDN in production.

---

## Files

All files in `design/`:

```
design/
├── Cockpit.html          — entrypoint, CSS tokens, font loading, React/Babel script tags
├── data.jsx              — META, LAPS, TRACK_POINTS, SECTOR_BOUNDS, TURNS, color utilities
├── cockpit-app.jsx       — App shell: state, tick loop, TopStrip, Scrubber
├── cockpit-car.jsx       — Car panel: chassis SVG + wheels + footer readouts
├── cockpit-lap.jsx       — Lap panel: big time, deltas, sectors, pace trace, projection
├── cockpit-map.jsx       — Map panel: Bahrain SVG, sectors, turns, car dot, HUD
└── cockpit-physics.jsx   — Physics panel: 4 tabs × 4 cornerwise CI charts
```

To view locally: open `Cockpit.html` in any modern browser. No build step — Babel transforms JSX in-browser.

---

## Implementation Notes for the Developer

1. **Port JSX verbatim, then restyle with the codebase's conventions.** The component structure is clean (one concern per panel) and the inline-style objects translate directly to CSS modules / styled-components / Tailwind utilities. Start by copying `cockpit-app.jsx` as the shell, then port each panel.

2. **Keep the single-source-of-truth tick loop.** Don't split `mode`/`pos`/`playing` across components — they're tightly coupled and the tick effect reads all three.

3. **The CI triplet shape is non-negotiable.** It's how the physics band renders and how uncertainty is communicated. If your real telemetry backend returns samples instead of CI triplets, compute 2.5/97.5 percentiles server-side and return triplets.

4. **Don't compress the type scale.** The 56px lap time is deliberate — in a race engineer's peripheral vision it needs to read from arm's length. Same reason everything is tabular mono with explicit tracking.

5. **Hover sync is critical.** The two-way highlight between the car SVG wheels, footer readouts, and physics charts is what makes the dashboard legible — it's the primary way the user traces "this tire is hot *and* it's degrading faster than expected." Don't drop it in the port.

6. **Accessibility todo (prototype does not address):**
   - Add ARIA labels to each panel region.
   - Make the scrubber keyboard-navigable (arrow keys = ±0.1 lap, shift-arrow = ±1 lap).
   - Mode toggle and speed buttons should be a proper `role="radiogroup"`.
   - Physics tabs should be `role="tablist"` / `role="tab"` / `role="tabpanel"`.
   - Color-only coding (sector colors, wear thresholds) should also carry text labels — they already mostly do.

7. **Responsive:** prototype is fixed to min-width 1600px. For smaller viewports, the panels should collapse to a vertical stack in the order: Car → Lap → Physics → Map. The Map and Physics panels both need their SVG viewBoxes preserved, so size them by aspect ratio, not viewport width.

8. **Tire geometry is hard-coded for a 400×780 viewBox.** If you want to change the car proportions, update `CAR.tires` in `cockpit-car.jsx` — everything else scales from those rectangles.
