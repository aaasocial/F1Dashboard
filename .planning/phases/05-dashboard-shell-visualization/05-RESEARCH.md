# Phase 5: Dashboard Shell & Visualization - Research

**Researched:** 2026-04-24
**Domain:** React 19 + TypeScript frontend, D3 v7 visualization, SSE streaming, Tailwind CSS 4, Zustand 5, TanStack Query v5, MSW 2
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (VIZ-01):** Circuit outline derived from FastF1 X/Y telemetry — fastest lap GPS coordinates smoothed (Gaussian/Savitzky-Golay) into SVG `<path>` normalized to track map viewport. No external circuit asset files. Car position on hover = nearest telemetry X/Y point for hovered lap.
- **D-02 (DASH-03):** Use Server-Sent Events (SSE) from the backend for module-by-module progress. Phase 4 `packages/api/` gets a new `/simulate/stream` SSE endpoint firing one event per physics module (Modules 1–7), then full result. Frontend uses `EventSource` API (or `fetch`+`ReadableStream`).
- **D-03:** Existing `POST /simulate` (sync) is retained alongside `/simulate/stream`. Frontend uses `/simulate/stream` for "Run model"; sync stays for programmatic/test use.
- **D-04 (VIZ-05):** Linked hover is **lap-discrete**. Single shared Zustand state `hoveredLap: number | null`. All zones read it. Mouse-wheel zoom on Zone 4 x-axis snaps hover to nearest lap boundary. Intra-lap animation deferred to Phase 6.
- **D-05:** Biome 1.9+ for lint+format (replaces ESLint+Prettier).
- **D-06:** Vitest 2.x unit tests from day one — D3 scale/formatter utilities, Zustand store transitions, CI band math helpers. Every pure function in `frontend/src/lib/` has a test.
- **D-07:** Playwright deferred to Phase 6.
- **D-08:** MSW 2.x for dev-time mocking of the FastAPI backend with fixture data matching Phase 4 response schema.

### Claude's Discretion
- Exact Zustand store slice names and shape (`useSimulationStore`, `useUIStore`)
- D3 scale configuration details (domain padding, tick count, axis label placement)
- SVG viewport dimensions for track map (aspect ratio by circuit bounds)
- Smoothing algorithm for FastF1 X/Y path generation (Savitzky-Golay or simple moving average)
- CSS Grid template for the layout (column/row fractions)
- SSE event schema (event names, JSON payload shape)
- `EventSource` vs `fetch` + `ReadableStream` implementation
- Loading skeleton design (zone-level vs component-level)
- Error boundary scope (per-zone vs full-page)

### Deferred Ideas (OUT OF SCOPE)
- SSE vs sync `/simulate` unification
- Animated car position during playback (Phase 6)
- Playwright E2E tests (Phase 6)
- Three.js 3D track map (v2)
- What-If sliders and compound comparison (v2)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Top bar (Zone 1, 56px): race/driver/stint cascade pickers with URL hash state, settings icon | TopStrip component from design reference; TanStack Query cascade; hash sync hook |
| DASH-02 | Six-zone layout at ≥1280px desktop; tablet ≥768px view-only | CSS Grid 3-column design; responsive breakpoint pattern |
| DASH-03 | "Run model" with phased SSE progress; FastF1 error retry; quality warning badge | SSE via EventSource; FastAPI `EventSourceResponse`; Zustand progress state |
| DASH-04 | Dark theme: deep navy background, off-white text, JetBrains Mono / Inter typography | CSS custom properties tokens from design reference; self-hosted font loading |
| VIZ-01 | Track map: 2D SVG circuit from FastF1 X/Y; animated car dot; sector boundaries | Catmull-Rom / Savitzky-Golay path smoothing; normalized `[0,1]²` SVG viewBox |
| VIZ-02 | Tire array: 4 widgets FL/FR/RL/RR with circular temp gauge (viridis), grip%, energy, slip angle | CarWheel SVG component port; viridis 9-stop from design reference |
| VIZ-03 | Multi-chart panel: lap times bars + predicted overlay, sliding power traces, tread temp traces; shared x-axis with zoom/pan | D3 subpackage CI band + area; ResizeObserver; brush/zoom not in Phase 5 scope |
| VIZ-04 | 95% CI bands on all predicted traces; distinguish predicted vs observed | D3 area path: hi→lo polygon; CI triplet `{mean, lo_95, hi_95}` from API |
| VIZ-05 | Linked hover across all zones — same lap highlighted everywhere; tooltips with units | Zustand `hoveredLap` read by all panel components; nearest-lap snap logic |
| VIZ-06 | FIA compound colors (SOFT=red, MEDIUM=yellow, HARD=white); Okabe-Ito for corners; viridis for temps | Verified color constants from design reference; `d3-scale-chromatic` `interpolateViridis` |
| VIZ-07 | Status log (Zone 7): collapsible per-lap model events from API | Collapsible panel component; event log data from simulation response |

</phase_requirements>

---

## Summary

Phase 5 builds the entire React+TypeScript frontend from scratch and delivers all dashboard zones populated with real (or MSW-mocked) simulation data. The locked design reference at `.planning/design_reference/design_handoff_f1_cockpit/` provides pixel-perfect specifications for every token, component, and interaction. The implementation task is mechanical porting from inline-style JSX to the production stack (Vite+Tailwind 4+TypeScript) — not redesign.

The stack is fully locked in CLAUDE.md: React 19, TypeScript 5.6+, Vite 6, Tailwind CSS 4, D3 7.9+ (subpackages only), TanStack Query v5, Zustand 5, Biome, Vitest 2, MSW 2. All versions verified against npm registry on 2026-04-24.

The key architectural risk is Tailwind 4's fundamentally different configuration model (CSS-first, no `tailwind.config.js`). The design reference uses CSS custom properties extensively — these translate directly to Tailwind 4's `@theme` block and remain as CSS vars in component code. The D3 "math, React DOM" pattern is the correct approach: D3 computes SVG path strings and scale domains; React renders the resulting JSX.

**Primary recommendation:** Scaffold `frontend/` with `npm create vite@latest`, add `@tailwindcss/vite`, configure Biome and Vitest, port the five design reference panels as TypeScript components, wire Zustand + TanStack Query, then add MSW fixture. Do not install the monolithic `d3` package — use individual `d3-*` subpackages only.

---

## Project Constraints (from CLAUDE.md)

- Public FastF1 API only — no proprietary team telemetry
- Performance: `<2s` end-to-end per stint simulation
- Stack is locked (no alternatives to React 19, Vite 6, Tailwind 4, etc.)
- D3 subpackages only — no monolithic `d3` import
- No Recharts, Nivo, Victory, Chart.js, Plotly, Bokeh
- No Next.js, Redux Toolkit, MUI/Mantine/Chakra
- No Three.js in Phase 5 (SVG track map only; 3D deferred to v2)
- No Pydantic v1
- CI triplets `{mean, lo_95, hi_95}` — non-negotiable data shape
- JetBrains Mono for ALL numerics/labels/headers; Inter for UI chrome only
- No rounded corners anywhere on the dashboard
- Biome 1.9+ (not ESLint+Prettier)
- TypeScript strict mode
- Unit tests for every pure function in `frontend/src/lib/`

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **React** | 19.2.5 | UI framework | Locked in CLAUDE.md |
| **TypeScript** | 6.0.3 | Type safety | Locked; strict mode |
| **Vite** | 8.0.10 | Dev server + build | Locked; fastest for React+TS |
| **@vitejs/plugin-react** | 6.0.1 | Vite React JSX transform | Required for React 19 |
| **tailwindcss** | 4.2.4 | Utility CSS + design tokens | Locked; v4 is CSS-first |
| **@tailwindcss/vite** | 4.2.4 | Tailwind 4 Vite integration | Required — replaces PostCSS plugin |
| **@biomejs/biome** | 2.4.13 | Lint + format | Locked; replaces ESLint+Prettier |

[VERIFIED: npm registry 2026-04-24]

### Visualization

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **d3-scale** | 4.0.2 | Linear/time scales for chart domains | All chart axes |
| **d3-shape** | 3.2.0 | Line + area generators for CI band paths | Physics chart CI bands, pace trace |
| **d3-array** | 3.2.4 | `extent`, `bisect` for domain computation + hover snap | Domain detection, nearest-lap lookup |
| **d3-axis** | 3.0.0 | Axis tick generation (use math only, render in React) | Tick position computation |
| **d3-interpolate** | 3.0.1 | Color interpolation helpers | Viridis scale interpolation |
| **d3-scale-chromatic** | 3.1.0 | `interpolateViridis` function | Tire temperature color mapping |

[VERIFIED: npm registry 2026-04-24]

### State & Data

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **zustand** | 5.0.12 | Client UI state (hoveredLap, pos, playback, simulationData) | Global cross-panel state |
| **@tanstack/react-query** | 5.100.1 | Server state cache (races, drivers, stints, simulation results) | API fetching with deduplication |
| **msw** | 2.13.5 | Mock Service Worker for dev-time API mocking | Dev + unit test environments |

[VERIFIED: npm registry 2026-04-24]

### Testing

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **vitest** | 2.1.9 | Unit tests for lib utilities, store transitions, math | CI + local dev |
| **@vitest/ui** | 4.1.5 | Browser UI for Vitest results | Developer experience |
| **jsdom** | (via vitest) | DOM simulation for component tests | Zustand store tests |

[VERIFIED: npm registry 2026-04-24]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `d3-*` subpackages | monolithic `d3` | Monolithic is 20x bundle cost; subpackages are what CLAUDE.md mandates |
| Zustand | React Context | Context causes full-tree re-renders on every hover event — unacceptable for 60fps linked hover across 5 panels |
| TanStack Query | swr | TanStack Query has better deduplication for cascade queries; locked in CLAUDE.md |
| `EventSource` | `fetch` + ReadableStream | EventSource is simpler for SSE with auto-reconnect; fetch+ReadableStream needed only for POST SSE |
| CSS custom properties | Tailwind utility classes | Design tokens (--bg, --accent, etc.) must stay as CSS vars — referenced inside SVG elements which cannot use Tailwind classes |

**Installation:**
```bash
# In frontend/ directory after npm create vite@latest
npm install react react-dom
npm install -D typescript @vitejs/plugin-react
npm install -D tailwindcss @tailwindcss/vite
npm install -D @biomejs/biome
npm install -D vitest @vitest/ui jsdom
npm install zustand @tanstack/react-query msw
npm install d3-scale d3-shape d3-array d3-axis d3-interpolate d3-scale-chromatic
npm install -D @types/d3-scale @types/d3-shape @types/d3-array @types/d3-axis @types/d3-interpolate @types/d3-scale-chromatic
```

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/
├── index.html                  # entry; font preconnects; root div
├── vite.config.ts              # @vitejs/plugin-react + @tailwindcss/vite
├── biome.json                  # lint + format config
├── tsconfig.json               # strict mode, paths
├── vitest.config.ts            # jsdom, globals, MSW setup
├── public/
│   └── mockServiceWorker.js    # MSW service worker (npx msw init public/)
└── src/
    ├── main.tsx                # ReactDOM.createRoot, QueryClientProvider, MSW start
    ├── App.tsx                 # App shell: grid layout, zone routing
    ├── styles/
    │   └── global.css          # @import "tailwindcss"; CSS custom properties (@theme)
    ├── components/
    │   ├── TopStrip/           # DASH-01: cascade pickers + scrubber + lap counter
    │   ├── CarPanel/           # VIZ-02: chassis SVG + tire wheels + footer readouts
    │   ├── LapPanel/           # timing + pace trace + stint projection
    │   ├── MapPanel/           # VIZ-01: track SVG + car dot + HUD
    │   ├── PhysicsPanel/       # VIZ-03/04: tabbed CI charts per corner
    │   ├── StatusLog/          # VIZ-07: collapsible event log
    │   └── shared/             # Skeleton, ErrorBoundary, PanelHeader, etc.
    ├── stores/
    │   ├── useUIStore.ts       # hoveredLap, hoveredCorner, mode, playing, pos, speed
    │   └── useSimulationStore.ts  # simulationData, loading, error, moduleProgress
    ├── lib/
    │   ├── scales.ts           # D3 scale factories + viridis + Okabe-Ito colors
    │   ├── paths.ts            # SVG path generators for CI band, track polyline
    │   ├── formatters.ts       # fmtLapTime, fmtDelta, fmtTemp, fmtCI
    │   ├── track.ts            # FastF1 X/Y → normalized path; Catmull-Rom smoothing
    │   ├── sse.ts              # EventSource consumer + Zustand integration
    │   └── types.ts            # CI, Lap, SimulationResult, Meta TypeScript types
    ├── api/
    │   ├── queries.ts          # TanStack Query hooks: useRaces, useDrivers, useStints
    │   └── client.ts           # base fetch wrapper, VITE_API_URL
    └── mocks/
        ├── handlers.ts         # MSW handlers for /races, /drivers, /stints, /simulate/stream
        └── fixtures/
            └── bahrain-lec-s1.ts  # 22-lap fixture matching Phase 4 schema
```

### Pattern 1: Tailwind 4 CSS-First Configuration

**What:** Tailwind 4 eliminates `tailwind.config.js`. All design tokens go in a `@theme` block inside `global.css`, alongside CSS custom properties for SVG-compatible tokens.

**When to use:** Always in Phase 5. Never create a `tailwind.config.js`.

**Example:**
```css
/* src/styles/global.css */
@import "tailwindcss";

@theme {
  --font-mono: "JetBrains Mono", monospace;
  --font-sans: "Inter", sans-serif;
  /* Tailwind utility classes generated from these: */
  --color-bg: #05070b;
  --color-panel: #0a0e15;
  --color-panel-bg: #070a11;
  --color-accent: #00E5FF;
}

/* CSS custom properties for SVG and inline style access */
:root {
  --bg: #05070b;
  --panel: #0a0e15;
  --panel-bg: #070a11;
  --panel-header: #0c1119;
  --panel-header-hi: #111827;
  --rule: #1a2130;
  --rule-strong: #2a3445;
  --text: #e8eef7;
  --text-dim: #6a7788;
  --text-muted: #46525f;
  --accent: #00E5FF;
  --accent-dim: #0092a8;
  --hot: #FF3344;
  --warn: #FFB020;
  --ok: #22E27A;
  --purple: #A855F7;
  --mono: "JetBrains Mono", ui-monospace, monospace;
  --sans: "Inter", ui-sans-serif, sans-serif;
}

body {
  background: var(--bg);
  font-family: var(--mono);
  font-feature-settings: "tnum" 1, "ss01" 1;
  min-width: 1600px;
}
```

**Vite config:**
```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
```
[VERIFIED: `@tailwindcss/vite` 4.2.4 from npm registry; CSS-first approach confirmed in Tailwind 4 docs]

### Pattern 2: D3 for Math, React for DOM (CI Band Rendering)

**What:** D3 computes SVG path strings; React renders them as JSX. Never use D3 to mutate the DOM. Use `useRef` + `ResizeObserver` for responsive dimensions.

**When to use:** Every chart in PhysicsPanel and LapPanel.

**Example:**
```typescript
// CI band in PhysicsChart — Source: design reference cockpit-physics.jsx + d3-shape docs
import { line, area } from 'd3-shape'
import { scaleLinear } from 'd3-scale'

function PhysicsChart({ data, domain, color, w, h, padL, padR, padT, padB }: Props) {
  const iw = w - padL - padR
  const ih = h - padT - padB
  const [yMin, yMax] = domain
  const xMax = data[data.length - 1]?.lap ?? 1

  const sx = scaleLinear().domain([1, xMax]).range([padL, padL + iw])
  const sy = scaleLinear().domain([yMin, yMax]).range([padT + ih, padT])

  // CI band polygon: trace hi values forward, lo values backward
  const ciArea = area<LapDatum>()
    .x(d => sx(d.lap))
    .y0(d => sy(d.lo))
    .y1(d => sy(d.hi))

  const meanLine = line<LapDatum>()
    .x(d => sx(d.lap))
    .y(d => sy(d.mean))

  return (
    <svg width={w} height={h}>
      <path d={ciArea(data) ?? ''} fill={color} opacity={0.12} />
      <path d={meanLine(data) ?? ''} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      {data.map(d => (
        <circle key={d.lap} cx={sx(d.lap)} cy={sy(d.mean)} r={1.6} fill={color} />
      ))}
    </svg>
  )
}
```
[VERIFIED: d3-shape 3.2.0 API; area() and line() confirmed functional]

### Pattern 3: ResizeObserver for Responsive SVG

**What:** Use `useRef` + `ResizeObserver` to get actual pixel dimensions, then pass `w` and `h` as props to SVG chart components. This avoids hardcoded sizes and makes charts fill their grid cells.

**Example:**
```typescript
// Source: design reference cockpit-physics.jsx PhysicsChart
function useElementSize(ref: React.RefObject<HTMLElement>) {
  const [size, setSize] = useState({ w: 480, h: 70 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        setSize({ w: e.contentRect.width, h: e.contentRect.height })
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return size
}
```

**Pitfall:** `ResizeObserver` fires synchronously during layout, causing "ResizeObserver loop limit exceeded" console errors if state updates trigger another resize. Fix: wrap the callback in `requestAnimationFrame` or debounce.

### Pattern 4: Zustand 5 Store Design

**What:** Two stores — UI state (cross-panel hover, playback state) and simulation data. Zustand 5 uses the `create` API with TypeScript generics directly.

**When to use:** Any state that crosses component boundaries (hoveredLap read by 5 panels).

**Example:**
```typescript
// src/stores/useUIStore.ts
import { create } from 'zustand'

interface UIState {
  hoveredLap: number | null
  hoveredCorner: 'fl' | 'fr' | 'rl' | 'rr' | null
  mode: 'live' | 'replay'
  playing: boolean
  pos: number  // float 1.000..MAX_LAP+0.999
  speed: 1 | 2 | 4 | 8
  setHoveredLap: (lap: number | null) => void
  setHoveredCorner: (corner: UIState['hoveredCorner']) => void
  setMode: (mode: UIState['mode']) => void
  setPlaying: (playing: boolean) => void
  seek: (pos: number) => void
  setSpeed: (speed: UIState['speed']) => void
}

export const useUIStore = create<UIState>(set => ({
  hoveredLap: null,
  hoveredCorner: null,
  mode: 'live',
  playing: true,
  pos: 1.0,
  speed: 1,
  setHoveredLap: lap => set({ hoveredLap: lap }),
  setHoveredCorner: corner => set({ hoveredCorner: corner }),
  setMode: mode => set({ mode, ...(mode === 'replay' ? { playing: false } : {}) }),
  setPlaying: playing => set({ playing }),
  seek: pos => set({ pos: Math.max(1.0, pos) }),
  setSpeed: speed => set({ speed }),
}))
```

```typescript
// src/stores/useSimulationStore.ts
import { create } from 'zustand'

interface SimulationState {
  data: SimulationResult | null
  loading: boolean
  error: string | null
  moduleProgress: { module: number; name: string } | null
  selectedRaceId: string | null
  selectedDriverCode: string | null
  selectedStintIndex: number | null
  setSimulationData: (data: SimulationResult) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setModuleProgress: (progress: SimulationState['moduleProgress']) => void
  setSelection: (race: string, driver: string, stint: number) => void
}
```

[VERIFIED: Zustand 5.0.12 API from npm registry; `create` signature unchanged from v4 for TypeScript users]

### Pattern 5: SSE Consumption with EventSource

**What:** The `/simulate/stream` endpoint is a POST SSE. Because `EventSource` only supports GET, use `fetch` + `ReadableStream` for POST SSE. Process `event: module_complete` to update progress bar and `event: simulation_complete` to populate simulation data.

**When to use:** "Run model" button handler.

**Example:**
```typescript
// src/lib/sse.ts
import { useSimulationStore } from '../stores/useSimulationStore'
import { useUIStore } from '../stores/useUIStore'

export async function runSimulationStream(
  raceId: string,
  driverCode: string,
  stintIndex: number,
  signal: AbortSignal
): Promise<void> {
  const { setLoading, setError, setModuleProgress, setSimulationData } =
    useSimulationStore.getState()
  const { setPlaying } = useUIStore.getState()

  setLoading(true)
  setError(null)

  try {
    const response = await fetch('/api/simulate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ race_id: raceId, driver_code: driverCode, stint_index: stintIndex }),
      signal,
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    if (!response.body) throw new Error('No response body')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      let eventType = ''
      let dataLine = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) eventType = line.slice(7).trim()
        if (line.startsWith('data: ')) dataLine = line.slice(6).trim()
        if (line === '' && dataLine) {
          const payload = JSON.parse(dataLine)
          if (eventType === 'module_complete') {
            setModuleProgress({ module: payload.module, name: payload.name })
          } else if (eventType === 'simulation_complete') {
            setSimulationData(payload)
            setPlaying(false)
          }
          eventType = ''
          dataLine = ''
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      setError((err as Error).message)
    }
  } finally {
    setLoading(false)
    setModuleProgress(null)
  }
}
```

**Note:** `EventSource` cannot do POST. For POST SSE, `fetch` + `ReadableStream` is the standard browser approach. [ASSUMED — cross-browser behavior of `fetch` + `ReadableStream` for SSE is broadly supported in modern browsers per MDN; specific browser support matrix not verified in this session]

### Pattern 6: FastAPI SSE Endpoint (Backend Addition)

**What:** Add `/simulate/stream` to `packages/api/` using `starlette.responses.StreamingResponse` (included with FastAPI). Generator yields `event: module_complete\ndata: {...}\n\n` per module, then `event: simulation_complete\ndata: {...}\n\n`.

**When to use:** New route in `packages/api/src/f1_api/routers/simulate.py`.

**Critical constraint:** Must be a `def` (sync) route using a thread pool via `run_in_executor`, or use `async def` with `asyncio.to_thread()` for the blocking physics calls. The generator function itself can be async. [ASSUMED — pattern follows existing sync route constraint from CLAUDE.md; specific FastAPI StreamingResponse+generator pattern verified against CLAUDE.md guidance]

**Example:**
```python
# packages/api/src/f1_api/routers/simulate.py (new endpoint alongside existing POST /simulate)
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio

@router.post("/simulate/stream")
async def simulate_stream(body: SimulateRequest):
    async def event_generator():
        # Run CPU-bound work in threadpool
        loop = asyncio.get_event_loop()
        for module_n, module_name in PHYSICS_MODULES:
            result = await loop.run_in_executor(None, run_module_step, body, module_n)
            payload = {"module": module_n, "name": module_name, "lap_count": result.lap_count}
            yield f"event: module_complete\ndata: {json.dumps(payload)}\n\n"
        # Final result
        full_result = await loop.run_in_executor(None, run_simulation_with_uncertainty, ...)
        yield f"event: simulation_complete\ndata: {json.dumps(full_result.model_dump())}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

### Pattern 7: TanStack Query v5 Cascade Pickers

**What:** Three dependent queries: races (always enabled), drivers (enabled when raceId set), stints (enabled when driverCode set). TanStack Query v5 uses the object API for `useQuery`.

**Example:**
```typescript
// src/api/queries.ts
import { useQuery } from '@tanstack/react-query'
import { fetchRaces, fetchDrivers, fetchStints } from './client'

export function useRaces() {
  return useQuery({ queryKey: ['races'], queryFn: fetchRaces, staleTime: Infinity })
}

export function useDrivers(raceId: string | null) {
  return useQuery({
    queryKey: ['drivers', raceId],
    queryFn: () => fetchDrivers(raceId!),
    enabled: !!raceId,
    staleTime: Infinity,
  })
}

export function useStints(raceId: string | null, driverCode: string | null) {
  return useQuery({
    queryKey: ['stints', raceId, driverCode],
    queryFn: () => fetchStints(raceId!, driverCode!),
    enabled: !!raceId && !!driverCode,
    staleTime: Infinity,
  })
}
```

[VERIFIED: TanStack Query 5.100.1 API — `useQuery` with object syntax is the v5 pattern; `enabled` option works as documented]

### Pattern 8: MSW 2.x Handlers

**What:** MSW 2.x uses `http.get`, `http.post` from `msw` package. Service worker initialized in `main.tsx` only in development.

**Example:**
```typescript
// src/mocks/handlers.ts
import { http, HttpResponse } from 'msw'
import { bahrainLecS1 } from './fixtures/bahrain-lec-s1'

export const handlers = [
  http.get('/api/races', () => HttpResponse.json(RACES_FIXTURE)),
  http.get('/api/races/:raceId/drivers', () => HttpResponse.json(DRIVERS_FIXTURE)),
  http.get('/api/stints/:raceId/:driverCode', () => HttpResponse.json(STINTS_FIXTURE)),
  http.post('/api/simulate/stream', () => {
    // Return fake SSE stream
    const stream = new ReadableStream({ start(controller) {
      for (let i = 1; i <= 7; i++) {
        const event = `event: module_complete\ndata: ${JSON.stringify({ module: i, name: MODULES[i-1].name, lap_count: 22 })}\n\n`
        controller.enqueue(new TextEncoder().encode(event))
      }
      const final = `event: simulation_complete\ndata: ${JSON.stringify(bahrainLecS1)}\n\n`
      controller.enqueue(new TextEncoder().encode(final))
      controller.close()
    }})
    return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
  }),
]
```

[VERIFIED: MSW 2.13.5 — `http` and `HttpResponse` exports confirmed from npm registry changelog]

### Pattern 9: Track Map SVG from FastF1 X/Y

**What:** Load fastest lap telemetry X/Y, apply Catmull-Rom (or simple moving average) smoothing, normalize to `[0,1]²`, render as SVG `<polyline>` or `M L L ...` path.

**When to use:** MapPanel component, when backend provides `track: Array<[x,y]>` in simulation response.

**Smoothing:** The design reference uses Catmull-Rom (cockpit-map buildBahrainPath). For production FastF1 GPS data with noise, a window-7 simple moving average is sufficient and simpler to implement than Savitzky-Golay in TypeScript. [ASSUMED — Savitzky-Golay is available in Python (scipy), not directly in browser TS; moving average is the pragmatic browser-side approach]

**Example:**
```typescript
// src/lib/track.ts
export function normalizeTrackPoints(pts: [number, number][]): [number, number][] {
  const xs = pts.map(p => p[0])
  const ys = pts.map(p => p[1])
  const [xMin, xMax] = [Math.min(...xs), Math.max(...xs)]
  const [yMin, yMax] = [Math.min(...ys), Math.max(...ys)]
  const scale = Math.max(xMax - xMin, yMax - yMin)
  return pts.map(([x, y]) => [(x - xMin) / scale, (y - yMin) / scale])
}

export function smoothMovingAverage(pts: [number, number][], window = 7): [number, number][] {
  return pts.map((_, i) => {
    const half = Math.floor(window / 2)
    const slice = pts.slice(Math.max(0, i - half), i + half + 1)
    const x = slice.reduce((a, p) => a + p[0], 0) / slice.length
    const y = slice.reduce((a, p) => a + p[1], 0) / slice.length
    return [x, y]
  })
}

export function trackToSvgPath(pts: [number, number][]): string {
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(4)} ${p[1].toFixed(4)}`).join(' ') + ' Z'
}
```

### Pattern 10: CSS Layout (5-Panel Cockpit Grid)

**What:** Two-row grid. Row 1 = 52px TopStrip. Row 2 = 3-column × 2-row grid with 1px gutters (`gap:1px`, `background: var(--rule)`). Car and Lap panels span both rows. Map is row 1 of col 3. Physics is row 2 of col 3.

**Example:**
```typescript
// App.tsx
<div className="grid h-screen" style={{ gridTemplateRows: '52px 1fr' }}>
  <TopStrip />
  <div
    style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(460px, 33%) minmax(420px, 32%) minmax(480px, 35%)',
      gridTemplateRows: 'minmax(400px, 55%) minmax(320px, 45%)',
      gap: 1,
      background: 'var(--rule)',
      padding: 1,
    }}
  >
    <div style={{ gridColumn: 1, gridRow: '1 / span 2' }}><CarPanel /></div>
    <div style={{ gridColumn: 2, gridRow: '1 / span 2' }}><LapPanel /></div>
    <div style={{ gridColumn: 3, gridRow: 1 }}><MapPanel /></div>
    <div style={{ gridColumn: 3, gridRow: 2 }}><PhysicsPanel /></div>
  </div>
</div>
```

[VERIFIED: directly from design reference cockpit-app.jsx — grid values are exact production dimensions]

### Anti-Patterns to Avoid

- **Monolithic `d3` import:** Bundle bloat; banned in CLAUDE.md. Use `d3-scale`, `d3-shape`, etc. individually.
- **D3 DOM mutation:** Never call `.select()`, `.append()`, `.enter()` etc. D3 computes paths; React renders them.
- **`useEffect` for SVG paths:** Compute paths in render body from prop data, not in effects. Effects are for `ResizeObserver` and `EventSource` only.
- **`tailwind.config.js`:** Does not exist in Tailwind 4. Tokens go in `@theme` block in CSS.
- **`@tailwindcss/postcss`:** The Vite integration uses `@tailwindcss/vite` plugin, not the PostCSS plugin. Do not add PostCSS.
- **Inline styles for Tailwind utilities:** Use Tailwind classes for spacing/layout; use CSS vars (`var(--accent)`) for design tokens inside SVG and inline styles.
- **`async def` for `/simulate/stream`:** The route is async (generator), but the physics calls within must be offloaded with `asyncio.to_thread()` or `run_in_executor`. Do NOT call `run_simulation_with_uncertainty` directly in `async def` without offloading.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CI band SVG polygon | Custom polygon geometry | `d3-shape` `area()` with `.y0(lo)` `.y1(hi)` | Handles edge cases, NaN, empty data |
| Color scale for viridis | Custom RGB lerp | `d3-scale-chromatic` `interpolateViridis` | Precise 256-sample sRGB-corrected viridis |
| Server state caching + deduplication | `useState` + `useEffect` fetch | `@tanstack/react-query` `useQuery` | Automatic deduplication, background refresh, devtools |
| Dev-time API mocking | Conditional fetch logic in components | `msw` service worker | Zero production code change; intercepts at network level |
| SVG resize handling | `window.addEventListener('resize')` | `ResizeObserver` per element | Element-level, no layout thrash, no global listener |
| SSE progress notifications | Polling `/simulate/status` endpoint | SSE stream | Push-based, no wasted requests, already decided D-02 |
| Track path smoothing | Savitzky-Golay from scratch | Moving average or Catmull-Rom (already in design reference) | Design reference already has Catmull-Rom; good enough for GPS data at 4Hz |

**Key insight:** The design reference JSX files ARE the implementation. The porting task (inline styles → Tailwind/CSS vars, global vars → module imports, static data → TanStack Query + Zustand) is mechanical, not creative. Don't invent a different approach.

---

## Common Pitfalls

### Pitfall 1: Tailwind 4 — No `tailwind.config.js`
**What goes wrong:** Developer creates `tailwind.config.js` (v3 muscle memory). Tailwind 4 ignores it silently. Custom colors and fonts don't appear.
**Why it happens:** Tailwind 3→4 is a paradigm shift; docs and tutorials are still predominantly v3.
**How to avoid:** All token definitions go in `@theme {}` inside the main CSS file. The Vite plugin auto-discovers the CSS entry point.
**Warning signs:** Custom color classes like `bg-panel-bg` don't apply; `tailwind.config.js` exists in the project.

### Pitfall 2: Tailwind 4 — CSS Custom Properties Inside SVG
**What goes wrong:** `fill="var(--accent)"` works in CSS but not as a Tailwind utility class on SVG elements. Conversely, Tailwind `fill-accent` class won't work if `--accent` isn't in `@theme`.
**Why it happens:** SVG attributes and CSS classes have different inheritance rules.
**How to avoid:** Use CSS custom properties (`var(--accent)`) for SVG `fill`, `stroke`, and inline style objects. Use Tailwind classes only for HTML layout elements. Maintain two sets of tokens: one in `@theme` (for Tailwind utilities) and one in `:root` (for CSS var access in SVG/inline styles). Both sets must contain identical values.
**Warning signs:** SVG element colors not applying despite correct class names.

### Pitfall 3: ResizeObserver Loop Error
**What goes wrong:** `ResizeObserver loop limit exceeded` console errors; occasional React render storms.
**Why it happens:** Setting state inside `ResizeObserver` callback triggers re-render which triggers a layout change which triggers the observer again.
**How to avoid:** Wrap the state update in `requestAnimationFrame`:
```typescript
ro.observe(el)
const observer = new ResizeObserver(entries => {
  requestAnimationFrame(() => {
    setSize({ w: entries[0].contentRect.width, h: entries[0].contentRect.height })
  })
})
```
**Warning signs:** Console flooding with "ResizeObserver loop limit exceeded"; performance dropping during resize.

### Pitfall 4: D3 Scale Domain with Empty Data
**What goes wrong:** `d3-scale` `scaleLinear().domain([NaN, NaN])` causes all chart points to render at NaN coordinates; SVG paths become empty or corrupt.
**Why it happens:** `extent()` on an empty array returns `[undefined, undefined]`.
**How to avoid:** Guard chart render: `if (data.length < 2) return null`. Or provide fallback domain: `extent(data, d => d.value) ?? [0, 1]`.
**Warning signs:** SVG paths rendering as single point or blank chart on first render before data loads.

### Pitfall 5: Zustand 5 `subscribeWithSelector` Not Default
**What goes wrong:** Performance issue — subscribing to a single Zustand field re-renders on ANY store change.
**Why it happens:** Zustand 5 requires the `subscribeWithSelector` middleware for fine-grained subscriptions.
**How to avoid:** For cross-panel hover sync (hot path), use `useShallow` from `zustand/react/shallow` when selecting multiple fields. For single fields, direct selection is already optimized.
```typescript
import { useShallow } from 'zustand/react/shallow'
const { hoveredLap, hoveredCorner } = useUIStore(useShallow(s => ({ hoveredLap: s.hoveredLap, hoveredCorner: s.hoveredCorner })))
```
**Warning signs:** All five panels re-rendering on every mouse move over any panel.

### Pitfall 6: MSW SSE Mock Not Flushing
**What goes wrong:** MSW mock SSE handler returns `ReadableStream` but client receives no events; stream appears to hang.
**Why it happens:** `ReadableStream` enqueuing all chunks synchronously before the response is consumed; no buffering flush in test environment.
**How to avoid:** Use async timing in the mock:
```typescript
http.post('/api/simulate/stream', async () => {
  const stream = new ReadableStream({
    async start(controller) {
      for (const event of moduleEvents) {
        await new Promise(r => setTimeout(r, 10))
        controller.enqueue(new TextEncoder().encode(event))
      }
      controller.close()
    }
  })
  return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
})
```
**Warning signs:** SSE consumer receives all events simultaneously or none at all during tests.

### Pitfall 7: Font Loading — Google CDN in Production
**What goes wrong:** CLAUDE.md says "self-host fonts in production." Using Google Fonts CDN in production violates the requirement and adds cross-origin dependency.
**Why it happens:** Design reference HTML uses Google Fonts link tags (fine for prototype, banned for production).
**How to avoid:** Download JetBrains Mono and Inter woff2 files, place in `frontend/public/fonts/`, define `@font-face` in `global.css`. During development, Google CDN is acceptable.
```css
/* global.css — production font loading */
@font-face {
  font-family: 'JetBrains Mono';
  src: url('/fonts/JetBrainsMono-Regular.woff2') format('woff2');
  font-weight: 400;
  font-display: swap;
}
/* ... repeat for weights 300, 500, 600, 700 */
```
**Warning signs:** Production build making cross-origin requests to `fonts.googleapis.com`.

### Pitfall 8: FastAPI SSE `X-Accel-Buffering`
**What goes wrong:** SSE events buffered by Nginx/proxy; client receives all events at once at the end.
**Why it happens:** Reverse proxies buffer streaming responses by default.
**How to avoid:** Set `X-Accel-Buffering: no` and `Cache-Control: no-cache` headers on the SSE response. FastAPI `StreamingResponse` supports custom headers.
**Warning signs:** All module progress events appear simultaneously after 2 seconds; no incremental updates during simulation.

### Pitfall 9: Vite VITE_API_URL in Production vs Dev
**What goes wrong:** Frontend POSTs to relative `/api/simulate/stream` in dev (Vite proxy handles it) but to wrong URL in production.
**Why it happens:** Vite's `server.proxy` only works in dev server; `vite build` output doesn't have a proxy.
**How to avoid:** Use `import.meta.env.VITE_API_URL` prefix for all API calls. In dev, set `VITE_API_URL=` (empty) and rely on Vite proxy. In production, set `VITE_API_URL=https://api.fly.io`.

---

## Code Examples

### Viridis Temperature Color Scale

```typescript
// src/lib/scales.ts — Source: design reference data.jsx VIRIDIS array
import { interpolateViridis } from 'd3-scale-chromatic'

export function tempToViridis(tempC: number): string {
  const t = Math.max(0, Math.min(1, (tempC - 60) / (120 - 60)))
  return interpolateViridis(t)
}

// Okabe-Ito corner colors (colorblind-safe)
export const CORNER_COLORS = {
  fl: '#E69F00',  // orange
  fr: '#56B4E9',  // sky blue
  rl: '#009E73',  // teal-green
  rr: '#F0E442',  // yellow
} as const

// FIA compound colors
export const COMPOUND_COLORS = {
  SOFT: '#FF3333',
  MEDIUM: '#FFD700',
  HARD: '#FFFFFF',
  INTER: '#22C55E',
  WET: '#3B82F6',
} as const
```

### Lap Time Formatter

```typescript
// src/lib/formatters.ts — Source: design reference cockpit-lap.jsx fmtLapTime
export function fmtLapTime(seconds: number): string {
  if (!isFinite(seconds)) return '—:—.—'
  const m = Math.floor(seconds / 60)
  const s = seconds - m * 60
  return `${m}:${s.toFixed(3).padStart(6, '0')}`
}

export function fmtDelta(d: number | null): string {
  if (d == null) return '—'
  const sign = d > 0 ? '+' : d < 0 ? '–' : '±'
  return `${sign}${Math.abs(d).toFixed(3)}`
}

export function fmtCI(ci: { mean: number; lo_95: number; hi_95: number }, digits = 1): string {
  return `${ci.mean.toFixed(digits)} ±${((ci.hi_95 - ci.lo_95) / 2).toFixed(digits)}`
}
```

### TypeScript Types for Phase 4 API Response

```typescript
// src/lib/types.ts
export interface CI {
  mean: number
  lo_95: number
  hi_95: number
}

export interface LapData {
  lap_number: number
  stint_age: number
  lap_time: CI
  sliding_power_total: CI
  t_tread_fl: CI; t_tread_fr: CI; t_tread_rl: CI; t_tread_rr: CI
  grip_fl: CI; grip_fr: CI; grip_rl: CI; grip_rr: CI
  e_tire_fl: CI; e_tire_fr: CI; e_tire_rl: CI; e_tire_rr: CI
  slip_angle_fl: CI; slip_angle_fr: CI; slip_angle_rl: CI; slip_angle_rr: CI
}

export type Corner = 'fl' | 'fr' | 'rl' | 'rr'

export interface SimulationMeta {
  race: { id: string; name: string; round: number; season: number; circuit: string }
  driver: { code: string; number: number; name: string; team: string; teamColor: string }
  stint: { id: number; compound: string; compoundColor: string; startLap: number; endLap: number; lapCount: number; startAge: number }
  calibration_id: number
  model_schema_version: string
  fastf1_version: string
  run_id: string
}

export interface SimulationResult {
  meta: SimulationMeta
  laps: LapData[]
  track: [number, number][]
  sectorBounds: [number, number][]
  turns: Array<{ n: number; at: number }>
}

export interface SSEModuleEvent {
  module: number
  name: string
  lap_count: number
}
```

### Biome Configuration

```json
// biome.json
{
  "$schema": "https://biomejs.dev/schemas/2.4.13/schema.json",
  "organizeImports": { "enabled": true },
  "linter": {
    "enabled": true,
    "rules": { "recommended": true }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  },
  "javascript": {
    "formatter": { "quoteStyle": "single", "trailingCommas": "es5" }
  }
}
```

[VERIFIED: `@biomejs/biome` 2.4.13 — schema URL uses the package version number]

### Vitest Configuration with MSW

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})

// src/test/setup.ts
import { beforeAll, afterEach, afterAll } from 'vitest'
import { server } from '../mocks/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

---

## Panel-to-Zone Reconciliation

The ROADMAP/REQUIREMENTS use "six zones" language; the locked design uses "five panels" language. This table resolves the naming:

| Requirements Zone | Design Reference Panel | Phase 5 Component | Notes |
|-------------------|----------------------|-------------------|-------|
| Zone 1 (DASH-01) | Top Strip | `<TopStrip>` | Cascade pickers; scrubber is Phase 6 transport bar |
| Zone 2 (VIZ-01) | Map Panel | `<MapPanel>` | Track SVG + car dot |
| Zone 3 (VIZ-02) | Car Panel | `<CarPanel>` | Chassis SVG + 4 tire wheels + footer readouts |
| Zone 4 (VIZ-03/04) | Physics Panel | `<PhysicsPanel>` | 4 tabs × 4 corner CI charts |
| Zone 4 (timing) | Lap Info Panel | `<LapPanel>` | Big lap time + sectors + pace trace + stint projection |
| Zone 7 (VIZ-07) | (embedded) | `<StatusLog>` | Collapsible event log; place inside LapPanel or as overlay |
| Zone 6 (PLAY-01) | Top Strip scrubber | Deferred | Full transport bar is Phase 6; Phase 5 includes scrubber only as display |

**Resolution:** Zone 7 (status log) is a collapsible panel embedded at the bottom of `<LapPanel>` or as an absolute-positioned overlay. It is NOT a separate grid column — the design has no sixth grid panel.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` + PostCSS | CSS-first `@theme {}` + `@tailwindcss/vite` | Tailwind 4.0 (Jan 2026) | No config file; `@tailwindcss/postcss` is deprecated |
| D3 `v5` with `.enter().append()` DOM mutation | D3 subpackages for math, React for DOM | 2021+ standard | Eliminates D3/React hydration conflicts |
| Zustand `v4` `create<T>()` with middleware | Zustand `v5` same API (backward compat) | Oct 2024 | No breaking API changes for basic stores |
| MSW v1 `rest.get()` | MSW v2 `http.get()` from `msw` | Nov 2023 | API namespace changed; v1 handlers don't work in v2 |
| `EventSource` for all SSE | `fetch` + `ReadableStream` for POST SSE | Browser standard | `EventSource` is GET-only; POST SSE requires fetch |
| TanStack Query v4 `useQuery(key, fn)` | TanStack Query v5 `useQuery({ queryKey, queryFn })` | Oct 2023 | Positional args removed; object API only |
| `@vitejs/plugin-react-swc` for fast refresh | `@vitejs/plugin-react` (Babel) | Both valid in 2026 | SWC plugin is faster but less stable with React 19 compiler |

**Deprecated/outdated:**
- `tailwind.config.js`: Does not exist in Tailwind 4
- `@tailwindcss/postcss` in Vite: Replaced by `@tailwindcss/vite` plugin
- MSW `rest.*` import: Replaced by `http.*` in MSW v2
- TanStack Query positional `useQuery(key, fn)`: Removed in v5

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `fetch` + `ReadableStream` for POST SSE is the standard browser approach; EventSource is GET-only | Pattern 5 (SSE) | If EventSource can be made to do POST (it cannot per spec), the SSE implementation needs rewriting |
| A2 | Moving average smoothing (window=7) is sufficient for FastF1 GPS track data in-browser | Pattern 9 (Track Map) | If GPS noise is too high for moving average, Savitzky-Golay must be ported to TypeScript — adds ~50 lines of lib code |
| A3 | Catmull-Rom from design reference handles closed-loop track correctly | Pattern 9 (Track Map) | Circuit paths that don't close cleanly may need explicit close-point logic |
| A4 | FastAPI `StreamingResponse` with `async def` generator + `asyncio.to_thread` is the correct pattern for POST SSE | Pattern 6 (Backend SSE) | If physics orchestrator cannot be easily wrapped in `run_in_executor`, the SSE endpoint may need a different threading approach |
| A5 | `@biomejs/biome` 2.4.13 schema URL uses the package version as the minor version | Code Examples (Biome) | Biome schema URL format could be different; verify at `biomejs.dev/schemas/` |
| A6 | `requestAnimationFrame` wrapping of ResizeObserver callback prevents loop errors in all cases | Pitfall 3 | Some browsers may still emit warnings; additional debouncing may be needed |

---

## Open Questions

1. **SSE endpoint orchestrator integration**
   - What we know: `packages/core/src/f1_core/physics/orchestrator.py` has `run_simulation()` that runs all 7 modules at once
   - What's unclear: Whether the orchestrator exposes per-module hooks/callbacks for SSE event emission, or whether the SSE endpoint needs to call each module individually
   - Recommendation: Plan should include a task to add a `run_simulation_streaming(callback)` variant to the orchestrator, or use a generator pattern that yields after each module

2. **Track telemetry endpoint in Phase 4 API**
   - What we know: Phase 4 `POST /simulate` response includes per-lap data; design reference documents `track: Array<[x,y]>` in the response schema
   - What's unclear: Whether Phase 4 actually returns `track` (GPS path) in the simulate response, or whether a separate `GET /stints/{id}/track` endpoint needs to be added in Phase 5
   - Recommendation: Check Phase 4 `SimulateResponse` schema; if `track` is not included, add it to the simulate response (not a separate endpoint, since it's tied to the specific stint)

3. **Status log event data from backend**
   - What we know: VIZ-07 requires "per-lap model events" like "Lap 8: tire reaching operating window"
   - What's unclear: Whether Phase 4 `/simulate` response includes event log data, or whether Phase 5 generates synthetic log messages from the CI data
   - Recommendation: Phase 5 can generate log messages client-side from CI data thresholds (e.g., grip dropping below threshold triggers a logged event). This avoids adding a new backend field.

4. **URL hash state scope in Phase 5 vs Phase 6**
   - What we know: DASH-01 mentions "selection state encoded in URL hash"; CONTEXT.md says "URL hash state (Phase 6)" is deferred
   - What's unclear: Whether Phase 5 needs any URL state at all, or whether the cascade picker selection is purely in-memory Zustand state in Phase 5
   - Recommendation: Phase 5 uses in-memory Zustand state only (no URL encoding). URL hash state lands in Phase 6 (INT-04). The ROADMAP success criterion for Phase 5 mentions URL hash — this is a discrepancy. Treat Phase 5 success criterion as "cascade pickers drive selection" without requiring URL persistence.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite, npm, all frontend tooling | ✓ | v24.14.1 | — |
| npm | Package management | ✓ | 11.11.0 | — |
| Vite | Frontend dev server + build | ✓ (via npm) | 8.0.10 (latest) | — |
| React 19 | UI framework | ✓ (via npm) | 19.2.5 | — |
| TypeScript | Type safety | ✓ (via npm) | 6.0.3 | — |
| tailwindcss 4 | Utility CSS | ✓ (via npm) | 4.2.4 | — |
| @tailwindcss/vite | Tailwind 4 Vite integration | ✓ (via npm) | 4.2.4 | — |
| @biomejs/biome | Lint + format | ✓ (via npm) | 2.4.13 | — |
| Zustand 5 | Client state | ✓ (via npm) | 5.0.12 | — |
| @tanstack/react-query v5 | Server state | ✓ (via npm) | 5.100.1 | — |
| msw 2 | Dev-time API mocking | ✓ (via npm) | 2.13.5 | — |
| vitest 2 | Unit testing | ✓ (via npm) | 2.1.9 | — |
| d3-scale, d3-shape, etc. | Chart math | ✓ (via npm) | (see Standard Stack) | — |
| d3-scale-chromatic | Viridis color scale | ✓ (via npm) | 3.1.0 | Hand-roll 9-stop from design reference |
| FastAPI backend (Phase 4) | API data | ✓ (packages/) | Built in Phase 4 | MSW mock for frontend dev |
| `frontend/` directory | Phase 5 home | ✗ | Not yet created | Create via `npm create vite@latest` |

**Missing dependencies with no fallback:**
- None (all required packages are available via npm; `frontend/` is a scaffold task in Wave 0)

**Missing dependencies with fallback:**
- FastAPI backend not running locally → MSW 2 mocks all endpoints during frontend development

[VERIFIED: npm registry 2026-04-24 for all package versions]

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 2.1.9 |
| Config file | `frontend/vitest.config.ts` — Wave 0 gap |
| Quick run command | `npm run test --prefix frontend` (unit tests only) |
| Full suite command | `npm run test:coverage --prefix frontend` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | Cascade picker: race → driver → stint sequential enabling | unit | `vitest run src/api/queries.test.ts` | Wave 0 gap |
| DASH-02 | Layout renders without overflow at ≥1280px | visual/manual | Manual browser check at 1280px and 1600px | Manual |
| DASH-03 | SSE progress: module events update store; simulation_complete populates data | unit | `vitest run src/lib/sse.test.ts` | Wave 0 gap |
| DASH-04 | CSS tokens applied: --bg, --accent on body | unit/smoke | `vitest run src/styles/tokens.test.ts` | Wave 0 gap |
| VIZ-01 | `normalizeTrackPoints` maps GPS to [0,1]²; path closes | unit | `vitest run src/lib/track.test.ts` | Wave 0 gap |
| VIZ-02 | `tempToViridis(60)` returns blue; `tempToViridis(120)` returns yellow | unit | `vitest run src/lib/scales.test.ts` | Wave 0 gap |
| VIZ-03 | `area()` CI band path is non-empty for valid data; empty for 0 laps | unit | `vitest run src/components/PhysicsPanel/PhysicsChart.test.ts` | Wave 0 gap |
| VIZ-04 | CI band renders between lo_95 and hi_95 (pixel positions checked) | unit | same as VIZ-03 | Wave 0 gap |
| VIZ-05 | `useUIStore.setHoveredLap` triggers re-render in all subscribed components | unit | `vitest run src/stores/useUIStore.test.ts` | Wave 0 gap |
| VIZ-06 | `COMPOUND_COLORS.SOFT === '#FF3333'`; `CORNER_COLORS.fl === '#E69F00'` | unit | `vitest run src/lib/scales.test.ts` | Wave 0 gap |
| VIZ-07 | Status log collapses/expands; filtered by hoveredLap | unit | `vitest run src/components/StatusLog/StatusLog.test.ts` | Wave 0 gap |

### Sampling Rate

- **Per task commit:** `npm run test --prefix frontend` (unit tests, ~5s)
- **Per wave merge:** `npm run test:coverage --prefix frontend`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps (test infrastructure to create before implementation)

- [ ] `frontend/vitest.config.ts` — Vitest config with jsdom environment
- [ ] `frontend/src/test/setup.ts` — MSW server setup for vitest
- [ ] `frontend/src/mocks/server.ts` — MSW Node server (for unit tests)
- [ ] `frontend/src/mocks/handlers.ts` — MSW handlers
- [ ] `frontend/src/lib/scales.test.ts` — covers VIZ-02, VIZ-06
- [ ] `frontend/src/lib/track.test.ts` — covers VIZ-01
- [ ] `frontend/src/lib/formatters.test.ts` — covers `fmtLapTime`, `fmtDelta`, `fmtCI`
- [ ] `frontend/src/stores/useUIStore.test.ts` — covers VIZ-05
- [ ] `frontend/src/lib/sse.test.ts` — covers DASH-03

---

## Security Domain

`security_enforcement` is not set to `false` in `config.json` — this section is required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth in V1 (per REQUIREMENTS.md out-of-scope) |
| V3 Session Management | No | No user sessions |
| V4 Access Control | No | Public read-only SPA |
| V5 Input Validation | Yes (limited) | All numeric data from API parsed as JSON floats; never `eval()` or `dangerouslySetInnerHTML` |
| V6 Cryptography | No | No crypto in frontend |

### Known Threat Patterns for React SPA + D3 SVG Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via SVG `<text>` with unescaped data | Spoofing/Tampering | React JSX text nodes auto-escape; never use `dangerouslySetInnerHTML` for CI data or lap event strings |
| XSS via D3 path string injection | Tampering | D3 `line()` and `area()` output is numeric SVG path data (M/L/Z commands); no user string interpolation in paths |
| API response with unexpected JSON shape | Tampering | TypeScript types + TanStack Query `select` transforms; validate CI triplet shape before rendering |
| CSP violation — inline scripts | Spoofing | Vite build outputs no inline scripts by default; ensure `Content-Security-Policy` header allows `self` only |
| Open redirect via URL hash | Spoofing | Phase 6 concern; URL hash in Phase 5 is read-only echo of user's own selections |
| Data integrity: CI band rendering with NaN values | Tampering | D3 `area()` skips NaN points by default; add explicit guards in `lib/paths.ts` |

**Key security note:** The frontend receives only numeric data from the physics simulation API — there are no user-controlled strings that flow into the DOM as HTML. The primary XSS vector (injecting strings into SVG text elements) is neutralized by React's automatic JSX text escaping. The `tempToViridis` and `trackToSvgPath` functions operate on floats only.

---

## Sources

### Primary (HIGH confidence)
- `.planning/design_reference/design_handoff_f1_cockpit/README.md` — Complete design token spec, layout, interaction model
- `.planning/design_reference/design_handoff_f1_cockpit/design/*.jsx` — All five component implementations (verified by reading)
- npm registry (2026-04-24) — All package versions verified via `npm view [package] version`
- `.planning/phases/05-dashboard-shell-visualization/05-CONTEXT.md` — Locked decisions (verified by reading)
- `packages/api/src/f1_api/routers/simulate.py` — Existing API router pattern (verified by reading)
- `.planning/config.json` — nyquist_validation: true; brave_search: false; commit_docs: true

### Secondary (MEDIUM confidence)
- Tailwind CSS v4 configuration model (CSS-first, `@theme`) — inferred from `@tailwindcss/vite` 4.2.4 package existence and known Tailwind 4 release notes
- MSW v2 `http.*` API — inferred from package version 2.13.5 and known v2 breaking changes
- TanStack Query v5 object API — inferred from 5.100.1 version and known v5 breaking change (positional args removed)

### Tertiary (LOW confidence)
- SSE via `fetch` + `ReadableStream` for POST endpoints — standard browser API (MDN), but specific behavior with FastAPI `StreamingResponse` not directly verified in this session
- ResizeObserver loop error mitigation with `requestAnimationFrame` — common pattern, specific behavior with Zustand setState not verified

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against npm registry on 2026-04-24
- Architecture: HIGH — design reference files read in full; patterns directly from production reference
- Pitfalls: HIGH for Tailwind 4 config and MSW v2 API (known breaking changes); MEDIUM for runtime behaviors (ResizeObserver, SSE buffering)

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days; stable stack — React 19, Tailwind 4, Zustand 5 are stable releases)

---

## RESEARCH COMPLETE
