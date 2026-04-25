# Phase 6: Playback, Interactions & Sharing - Research

**Researched:** 2026-04-25
**Domain:** React interactive dashboard — keyboard events, SVG export, D3 zoom, XHR upload, URL hash, context menus
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**A — Transport Bar & Step Controls**
- D-01: All playback controls stay in TopStrip. No new layout row. Grid remains `52px 1fr`.
- D-02: Step ±1 lap = `seek(pos ± 1)` clamped to `[1, maxLap]`. Jump first/last = `seek(1)` / `seek(maxLap)`.
- D-03: Speed set is 0.5×/1×/2×/4×. Remove 8×. Add 0.5×.
- D-04: Scrubber upgraded to sector-colored segments (`#3a98b4` / `#2a7a93` / `#1d6278`). Pit-stop lap markers as white tick marks at `stint_age === 0` laps.

**B — Keyboard Shortcuts**
- D-05: Global `keydown` in `App.tsx`. All shortcuts fire when no input is focused.
- D-06: T = MapPanel fullscreen overlay, `position: fixed`, `z-index: 100`, backdrop blur. Grid underneath untouched.
- D-07: E = toggle `statusLogCollapsed` in `useUIStore`; `StatusLog` gains `collapsed` prop; `max-height` CSS transition to 0.
- D-08: S = `navigator.clipboard.writeText(window.location.href)` + `position: fixed` toast, `URL COPIED`, `var(--accent)`, 2s.
- D-09: ? = centered modal overlay with two-column monospace shortcut table. Esc or backdrop click dismisses.

**C — Chart Export**
- D-10: Right-click on PhysicsChart/PhysicsPanel → custom context menu overlay (not native browser menu). Dark panel background, `var(--rule)` border, items: Export PNG / Export SVG / Export CSV. Dismissed by click-outside or Esc.
- D-11: Export scope = current metric tab, all 4 corners (full 4-chart column).
- D-12: PNG export = foreignObject-free SVG-to-canvas: serialize SVG string → `<img src="data:image/svg+xml,...">` → `<canvas>` drawImage → `canvas.toBlob()` → download. No html2canvas.
- D-13: SVG export = clone SVG element, inline computed styles for `font-family` and `fill`, trigger download as `.svg`. No dependency.
- D-14: CSV export = build string from `data.laps` for active metric, download via `URL.createObjectURL(new Blob([csv], {type:'text/csv'}))`.
- D-15: Tire widget clipboard copy = right-click CarWheel/CarFooter → `navigator.clipboard.writeText("FL | 94.2°C | Grip 1.31μ | Wear 3.2 MJ | Slip 2.1°")`. Same toast pattern as D-08.

**D — Drag-and-Drop Session Upload**
- D-16: Global `dragenter`/`dragleave`/`drop` on `document.body` in `useDragUpload` hook. Full-app drop overlay with dashed accent border and `DROP FASTF1 CACHE ZIP HERE` message.
- D-17: Validate `.zip` extension → `POST /sessions/upload` multipart/form-data → `XMLHttpRequest` for upload progress bar. On success store `session_id` in `useSimulationStore`, auto-trigger `/simulate`. On error show error banner.
- D-18: Backend `/sessions/upload` already implemented in Phase 4. Frontend hook + UI only.

**E — Provenance Footer**
- D-19: ⓘ button in TopStrip right block → centered modal with monospace provenance table (FastF1 version, model schema version, calibration ID, calibration date, run ID, disclaimer). Esc or backdrop dismisses.
- D-20: Data sourced from `data.meta` (`fastf1_version`, `model_schema_version`, `calibration_id`, `run_id`). Calibration date = N/A if not in schema.

**F — Error/Retry UI (SC-3 carry-in)**
- D-21: Dismissable red error banner below TopStrip reading `useSimulationStore(s => s.error)`. RETRY button re-runs `runSimulationStream`. Auto-dismissed on next successful run.

**G — PhysicsPanel Zoom/Pan (SC-4 carry-in)**
- D-22: Shared `xZoom: [number, number] | null` in `useUIStore`. All 4 PhysicsChart components read `xZoom` as D3 scale domain. Wheel event on any chart updates `xZoom`. Drag pans. "↺ RESET" button in PhysicsPanel tab strip when zoomed.

**H — Testing**
- D-23: Playwright E2E tests in Phase 6: (1) pick stint → run → panels populate, (2) keyboard shortcuts advance playback, (3) export downloads a file, (4) URL hash round-trip.

### Claude's Discretion
- Exact pixel placement and sizing of step/jump buttons in TopStrip
- Toast implementation (no library — `position: fixed` div with `setTimeout` unmount)
- Sector color boundaries on Scrubber derived from `sectorBounds` in simulation result
- CSS `max-height` transition duration for StatusLog collapse animation
- Whether `xZoom` resets on new simulation load (yes — reset to full range on `setData`)
- Context menu positioning (ensure it doesn't overflow viewport edges)

### Deferred Ideas (OUT OF SCOPE)
- Intra-lap 4Hz continuous animation — v2
- Three.js 3D track map — v2
- What-If sliders and compound comparison — v2
- SSE/sync endpoint unification — v2
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAY-01 | Transport bar with play/pause, step ±1 lap, jump first/last, speed control (0.5×/1×/2×/4×), sector-colored scrub bar, lap readout | D-01 through D-04; extend existing TopStrip/Scrubber |
| PLAY-02 | Playback animates car position on track SVG, advances chart playhead, updates tire array in sync without stutter | RAF loop already exists in App.tsx; zoom state added to PhysicsChart |
| INT-01 | Global keyboard shortcuts: Space, ←/→, Shift+←/→, Home/End, 1/2/3/4, T, E, S, ?, Esc | Document `keydown` in `useEffect`; input focus guard pattern |
| INT-02 | Right-click chart → context menu → PNG/SVG/CSV export | SVG-to-canvas foreignObject-free pattern; computed style inline; Blob download |
| INT-03 | Right-click tire widget → clipboard copy of formatted metric string | `navigator.clipboard.writeText`; toast pattern |
| INT-04 | URL hash encodes full scenario; pasting URL restores exact view | Extend existing `useHashSync`; add `pos` + param overrides to hash |
| INT-05 | Drag-and-drop FastF1 zip → POST /sessions/upload → auto simulate | `useDragUpload` hook; XHR progress; `session_id` threading |
| INT-06 | Provenance footer: FastF1 version, model schema version, calibration ID, calibration date, disclaimer | ⓘ modal reading `data.meta`; always visible |
</phase_requirements>

---

## Summary

Phase 6 is a pure frontend interaction layer that sits on top of the Phase 5 visualization substrate. No backend changes are needed except calling the already-implemented `/sessions/upload` endpoint. The work falls into eight discrete feature areas, each with a natural implementation unit: store extension, a hook, a UI component, or an event handler.

The most technically nuanced areas are SVG export (CORS font-taint, computed style stripping, canvas serialization), D3 zoom/pan coordination across four independent React SVG components via shared Zustand state, and keyboard event handling with correct input-focus exclusion. All three have well-established patterns in the 2025–2026 React ecosystem that this research documents with verified examples.

The existing codebase is in excellent shape for Phase 6: `useUIStore` already has `pos`, `seek`, `togglePlaying`, `speed`; `Scrubber` already has pointer drag logic; `PhysicsChart` already has `onMouseMove`/`onMouseLeave` and a `ref` for resize; `App.tsx` already has the RAF loop and `useHashSync` is already wired. Phase 6 extends rather than rewrites everything.

**Primary recommendation:** Implement in this order: (1) store additions + speed fix, (2) step/jump buttons + speed array correction, (3) scrubber sector coloring, (4) keyboard shortcuts, (5) zoom/pan, (6) chart export, (7) tire clipboard, (8) drag-and-drop upload, (9) provenance modal, (10) error banner, (11) Playwright tests. Each area is independent after the store is updated.

---

## Standard Stack

### Core (already installed — no new installs)
| Library | Version in Use | Purpose | Phase 6 Usage |
|---------|---------------|---------|---------------|
| **React** | 19.2.5 | UI framework | All new components |
| **TypeScript** | 6.0.3 | Type safety | Store extensions, hook types |
| **Zustand** | 5.0.12 | Client state | `useUIStore` additions; `useSimulationStore` `session_id` |
| **D3 (subpackages)** | d3-scale 4.x, d3-shape 3.x | Math | Zoom domain recalculation; scrubber segment widths |
| **Vitest** | 2.1.9 | Unit tests | Hook logic tests |
| **MSW** | 2.13.5 | API mocks | Upload endpoint mock for tests |

### New Install Required
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **@playwright/test** | 1.59.1 (current in registry) | E2E tests | D-23 requires it; not yet installed [VERIFIED: npm registry] |

**Installation:**
```bash
cd frontend && npm install --save-dev @playwright/test
npx playwright install chromium  # install headless browser binary
```

### Alternatives Considered (rejected per CONTEXT.md decisions)
| Instead of | Could Use | Why Rejected |
|------------|-----------|--------------|
| Manual SVG-to-canvas | html2canvas | D-12 explicitly rejects it; brings CORS complexity |
| Custom toast | react-hot-toast or sonner | D-08 explicitly rejects library dependency |
| Custom context menu | radix-ui DropdownMenu | D-10 explicitly requires custom dark panel menu |

---

## Architecture Patterns

### Store Extension Pattern (useUIStore)

The existing store interface must be extended. New fields per CONTEXT.md decisions:

```typescript
// [VERIFIED: codebase read — useUIStore.ts line 4-18]
// Add to UIState interface:
interface UIState {
  // ... existing fields ...
  speed: 0.5 | 1 | 2 | 4          // was: 1 | 2 | 4 | 8
  statusLogCollapsed: boolean      // D-07
  xZoom: [number, number] | null   // D-22 — null = full range
  mapFullscreen: boolean           // D-06
  shortcutsOpen: boolean           // D-09
  provenanceOpen: boolean          // D-19
  // Actions:
  setStatusLogCollapsed: (v: boolean) => void
  toggleStatusLog: () => void
  setXZoom: (domain: [number, number] | null) => void
  setMapFullscreen: (v: boolean) => void
  setShortcutsOpen: (v: boolean) => void
  setProvenanceOpen: (v: boolean) => void
}
```

**Critical:** The `speed` type union must change from `1 | 2 | 4 | 8` to `0.5 | 1 | 2 | 4`. All callers of `setSpeed` must be updated. The RAF animation uses `speed` as a multiplier directly — `0.5` works correctly with the existing arithmetic (`dt * speed / LAP_SECONDS`). [VERIFIED: codebase read — App.tsx line 43, useUIStore.ts line 17]

### useSimulationStore Extension

Add `session_id` for upload flow (D-17):

```typescript
// Add to SimulationState:
sessionId: string | null
setSessionId: (id: string | null) => void
```

The `lastRunParams` must also be stored for retry (D-21):

```typescript
lastRunParams: { raceId: string; driverCode: string; stintIndex: number } | null
setLastRunParams: (p: { raceId: string; driverCode: string; stintIndex: number } | null) => void
```

### Global Keyboard Shortcut Handler

**Pattern:** `document.addEventListener` in a `useEffect` in `App.tsx`. The handler must guard against input elements being focused to avoid intercepting user typing.

```typescript
// [ASSUMED] Standard React keyboard shortcut pattern — widely used, matches CONTEXT.md D-05
useEffect(() => {
  function handler(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
    if ((e.target as HTMLElement)?.isContentEditable) return

    const { pos, seek, togglePlaying, setHoveredCorner, setMapFullscreen, toggleStatusLog, setShortcutsOpen } = useUIStore.getState()
    const { data } = useSimulationStore.getState()
    const maxLap = data?.laps.length ?? 22

    switch (true) {
      case e.code === 'Space':
        e.preventDefault()  // prevent page scroll
        togglePlaying()
        break
      case e.code === 'ArrowLeft' && !e.shiftKey:
        e.preventDefault()
        seek(Math.max(1, Math.floor(pos) - 1))
        break
      case e.code === 'ArrowRight' && !e.shiftKey:
        e.preventDefault()
        seek(Math.min(maxLap, Math.floor(pos) + 1))
        break
      case e.code === 'Home':
        e.preventDefault()
        seek(1)
        break
      case e.code === 'End':
        e.preventDefault()
        seek(maxLap)
        break
      case e.key === '1': setHoveredCorner('fl'); break
      case e.key === '2': setHoveredCorner('fr'); break
      case e.key === '3': setHoveredCorner('rl'); break
      case e.key === '4': setHoveredCorner('rr'); break
      case e.key === 't' || e.key === 'T':
        setMapFullscreen(!useUIStore.getState().mapFullscreen)
        break
      case e.key === 'e' || e.key === 'E':
        toggleStatusLog()
        break
      case e.key === 's' || e.key === 'S':
        void navigator.clipboard.writeText(window.location.href)
        // trigger toast via store or local ref
        break
      case e.key === '?':
        setShortcutsOpen(true)
        break
      case e.code === 'Escape':
        setMapFullscreen(false)
        setShortcutsOpen(false)
        useUIStore.getState().setProvenanceOpen(false)
        break
    }
  }
  document.addEventListener('keydown', handler)
  return () => document.removeEventListener('keydown', handler)
}, [])  // empty deps — reads state via .getState() to avoid stale closures
```

**Critical:** Use `useUIStore.getState()` / `useSimulationStore.getState()` inside the handler, not hook values, to avoid stale closures in the `useEffect`. This is the standard pattern for Zustand event listeners. [ASSUMED]

**Shift+← / Shift+→ sector jump:** The simulation result does not have explicit sector-by-lap boundaries (only track geometry `sectorBounds` which is an index into the `track[]` array). For keyboard sector jumps, derive sector boundaries from lap count: S1 ends at `floor(maxLap / 3)`, S2 at `floor(2 * maxLap / 3)`, S3 at `maxLap`. This is an approximation — if `sectorBounds` carries lap indices in the simulation result it should be used directly.

### SVG Export: foreignObject-Free PNG Pattern

**Problem:** React renders SVG with CSS custom properties (`var(--text)`, `var(--mono)`) and `font-family` references to self-hosted fonts. When serialized to a data URL and drawn on `<canvas>`, browsers cannot resolve CSS variables or load fonts from a different origin context — producing blank text or missing colors. [ASSUMED — widely documented browser security behavior]

**Solution:**

```typescript
// [ASSUMED] Standard pattern for SVG-to-canvas without foreignObject
async function exportPng(svgEl: SVGElement): Promise<void> {
  // 1. Clone SVG — do not mutate the live DOM
  const clone = svgEl.cloneNode(true) as SVGElement

  // 2. Walk clone, replace CSS custom properties with computed values
  inlineComputedStyles(clone, svgEl)

  // 3. Ensure explicit width/height attributes (required by some browsers)
  const bbox = svgEl.getBoundingClientRect()
  clone.setAttribute('width', String(bbox.width))
  clone.setAttribute('height', String(bbox.height))

  // 4. Serialize to data URL
  const serializer = new XMLSerializer()
  const svgStr = serializer.serializeToString(clone)
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgStr)}`

  // 5. Draw to canvas via img element
  await new Promise<void>((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = bbox.width * (window.devicePixelRatio || 1)
      canvas.height = bbox.height * (window.devicePixelRatio || 1)
      const ctx = canvas.getContext('2d')!
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1)
      ctx.drawImage(img, 0, 0)
      canvas.toBlob(blob => {
        if (!blob) return reject(new Error('toBlob failed'))
        triggerDownload(URL.createObjectURL(blob), 'physics-chart.png')
        resolve()
      }, 'image/png')
    }
    img.onerror = reject
    img.src = url
  })
}
```

**Computing styles for the clone:**

```typescript
// [ASSUMED] Traverse all elements in clone, resolve CSS custom properties
function inlineComputedStyles(clone: Element, source: Element): void {
  const sourceStyle = window.getComputedStyle(source)
  const attrs = ['fill', 'stroke', 'color', 'font-family', 'font-size', 'font-weight']

  for (const attr of attrs) {
    const val = sourceStyle.getPropertyValue(attr).trim()
    if (val && !val.startsWith('var(')) {
      ;(clone as HTMLElement).style?.setProperty(attr, val)
    }
  }
  // CSS custom properties: manually resolve the ones used in PhysicsChart
  const cssVarMap: Record<string, string> = {
    '--text': '#e8eef7',
    '--text-muted': '#46525f',
    '--text-dim': '#6a7788',
    '--rule': '#1a2130',
    '--rule-strong': '#2a3445',
    '--accent': '#00E5FF',
    '--panel': '#0a0e15',
    '--mono': 'JetBrains Mono, monospace',
  }
  // Walk all elements in clone
  const allSource = source.querySelectorAll('*')
  const allClone = clone.querySelectorAll('*')
  allSource.forEach((srcEl, i) => {
    const cloneEl = allClone[i] as HTMLElement
    if (!cloneEl) return
    const cs = window.getComputedStyle(srcEl)
    for (const [cssVar, fallback] of Object.entries(cssVarMap)) {
      const resolved = cs.getPropertyValue(cssVar).trim() || fallback
      // If the element has a fill/stroke set to the CSS var, replace it
    }
    // Simpler: hardcode the token values as SVG presentation attributes
    const fill = cloneEl.getAttribute('fill') ?? ''
    if (fill.startsWith('var(')) {
      const varName = fill.slice(4, -1)
      cloneEl.setAttribute('fill', cssVarMap[varName] ?? '#e8eef7')
    }
    const stroke = cloneEl.getAttribute('stroke') ?? ''
    if (stroke.startsWith('var(')) {
      const varName = stroke.slice(4, -1)
      cloneEl.setAttribute('stroke', cssVarMap[varName] ?? '#1a2130')
    }
  })
}
```

**Simpler approach (recommended):** Since all CSS token values are hardcoded constants in `CLAUDE.md`, just do a string replace on the serialized SVG before creating the data URL:

```typescript
// Replace var(--token) with its literal value in the serialized SVG string
const TOKEN_MAP: Record<string, string> = {
  'var(--bg)': '#05070b',
  'var(--panel)': '#0a0e15',
  'var(--panel-bg)': '#070a11',
  'var(--rule)': '#1a2130',
  'var(--rule-strong)': '#2a3445',
  'var(--text)': '#e8eef7',
  'var(--text-dim)': '#6a7788',
  'var(--text-muted)': '#46525f',
  'var(--accent)': '#00E5FF',
  'var(--hot)': '#FF3344',
  'var(--warn)': '#FFB020',
  'var(--ok)': '#22E27A',
  'var(--purple)': '#A855F7',
  'var(--mono)': 'JetBrains Mono, monospace',
}

let svgStr = serializer.serializeToString(clone)
for (const [varRef, value] of Object.entries(TOKEN_MAP)) {
  svgStr = svgStr.replaceAll(varRef, value)
}
```

This approach is more reliable than traversing computed styles because the tokens are stable constants. [ASSUMED — based on how CSS token substitution works; the hardcoded values are locked in CLAUDE.md]

**Font rendering in exported PNG:** Self-hosted fonts (JetBrains Mono) will NOT render in canvas unless the font data is embedded in the SVG as a base64 `<style>` block. For the monospace labels in PhysicsChart, the fallback `monospace` system font is acceptable in exports — the data values will still be legible. If perfect font fidelity is required, embed the WOFF2 as a data URL in a `<defs><style>` block. This is out of scope for Phase 6 (D-12 does not specify font fidelity requirements). [ASSUMED]

### SVG Export: Direct SVG Download

```typescript
function exportSvg(svgEl: SVGElement, filename = 'physics-chart.svg'): void {
  const clone = svgEl.cloneNode(true) as SVGElement
  // Same CSS var substitution as above (string replace on serialized output)
  const serializer = new XMLSerializer()
  let svgStr = serializer.serializeToString(clone)
  for (const [varRef, value] of Object.entries(TOKEN_MAP)) {
    svgStr = svgStr.replaceAll(varRef, value)
  }
  // Add XML declaration for standalone SVG files
  const blob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${svgStr}`], {
    type: 'image/svg+xml;charset=utf-8',
  })
  triggerDownload(URL.createObjectURL(blob), filename)
}
```

### CSV Export

```typescript
// [VERIFIED: codebase read — types.ts; LapData shape confirmed]
function exportCsv(
  laps: LapData[],
  metricKey: 't_tread' | 'grip' | 'e_tire' | 'slip_angle',
  filename = 'physics-data.csv'
): void {
  const corners = ['fl', 'fr', 'rl', 'rr'] as const
  const header = [
    'lap',
    ...corners.flatMap(c => [`${c}_mean`, `${c}_lo95`, `${c}_hi95`]),
  ].join(',')

  const rows = laps.map(lap => {
    const values = corners.flatMap(c => {
      const ci = lap[`${metricKey}_${c}` as keyof LapData] as CI
      return [ci.mean.toFixed(4), ci.lo_95.toFixed(4), ci.hi_95.toFixed(4)]
    })
    return [lap.lap_number, ...values].join(',')
  })

  const csv = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  triggerDownload(URL.createObjectURL(blob), filename)
}

// Shared download trigger
function triggerDownload(url: string, filename: string): void {
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
```

**D-11 scope:** Export scope is the full 4-chart column for the active metric. The `PhysicsPanel` component wraps all 4 `PhysicsChart` instances in one container div. The `onContextMenu` handler should be on the `PhysicsPanel` container (or delegated from a wrapper), so one right-click captures the entire column's SVG. The individual `PhysicsChart` SVG elements can be queried with `containerRef.current.querySelectorAll('svg')` and composed into a single tall SVG.

### D3 Zoom/Pan: Shared xZoom State Pattern

**Problem:** Four separate `PhysicsChart` components each have independent D3 scale objects. Standard D3 zoom attaches to a DOM element and owns the transform state — if each chart owns its own zoom behavior, they won't stay synchronized. [ASSUMED — based on D3 zoom architecture]

**Solution (per D-22):** Store the zoom domain as `xZoom: [number, number] | null` in `useUIStore`. Each `PhysicsChart` reads `xZoom` and uses it as the D3 scale domain, bypassing D3's built-in zoom behavior entirely. Wheel and drag events are handled with standard DOM events, not `d3.zoom()`.

```typescript
// In PhysicsChart.tsx — add to the component:
const xZoom = useUIStore(s => s.xZoom)
const setXZoom = useUIStore(s => s.setXZoom)
const maxLap = props.maxLap

// Effective domain: use xZoom if set, else full range
const [domainStart, domainEnd] = xZoom ?? [1, maxLap]
const sx = scaleLinear().domain([domainStart, domainEnd]).range([padL, padL + iw])

// Wheel handler — zoom in/out centered on cursor lap
function onWheel(e: React.WheelEvent) {
  e.preventDefault()
  const current = useUIStore.getState().xZoom ?? [1, maxLap]
  const [d0, d1] = current
  const range = d1 - d0
  const factor = e.deltaY > 0 ? 1.15 : 0.87  // scroll up = zoom in
  const newRange = range * factor
  // Clamp to [1, maxLap]
  const center = (d0 + d1) / 2
  const newD0 = Math.max(1, center - newRange / 2)
  const newD1 = Math.min(maxLap, newD0 + newRange)
  if (newD1 - newD0 >= 1) setXZoom([newD0, newD1])
}

// Drag-to-pan — track pointer delta on the scale
const dragStartRef = useRef<{ x: number; domain: [number, number] } | null>(null)
function onPointerDown(e: React.PointerEvent) {
  dragStartRef.current = {
    x: e.clientX,
    domain: useUIStore.getState().xZoom ?? [1, maxLap],
  }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
function onPointerMove(e: React.PointerEvent) {
  if (!dragStartRef.current) return
  const dx = e.clientX - dragStartRef.current.x
  const [d0, d1] = dragStartRef.current.domain
  const lapPerPx = (d1 - d0) / iw  // laps per pixel
  const shift = -dx * lapPerPx
  const newD0 = Math.max(1, d0 + shift)
  const newD1 = Math.min(maxLap, newD0 + (d1 - d0))
  setXZoom([newD0, newD1])
}
function onPointerUp() { dragStartRef.current = null }
```

**Reset button:** In `PhysicsPanel` tab strip, render a `"↺ RESET"` button when `xZoom !== null`:

```typescript
const xZoom = useUIStore(s => s.xZoom)
const setXZoom = useUIStore(s => s.setXZoom)

{xZoom !== null && (
  <button onClick={() => setXZoom(null)} style={{ ... }}>↺ RESET</button>
)}
```

**xZoom reset on new simulation:** In `useSimulationStore.setSimulationData`, also call `useUIStore.getState().setXZoom(null)`. This couples the two stores — acceptable since it is explicitly decided in CONTEXT.md. [VERIFIED: CONTEXT.md — discretion section: "xZoom resets on new simulation load (yes — reset to full range on setData)"]

### Drag-and-Drop Upload: useDragUpload Hook

**Problem:** `fetch` does not expose upload progress events. `XMLHttpRequest` does. [ASSUMED — well-known browser API limitation; no fetch upload progress streaming in 2026]

```typescript
// [ASSUMED] Standard XHR upload pattern with progress
function uploadFile(
  file: File,
  onProgress: (pct: number) => void
): Promise<{ session_id: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const formData = new FormData()
    formData.append('file', file)

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total)
    })
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`))
      }
    })
    xhr.addEventListener('error', () => reject(new Error('Network error')))

    const apiBase = import.meta.env.VITE_API_URL ?? ''
    xhr.open('POST', `${apiBase}/api/sessions/upload`)
    xhr.send(formData)
  })
}
```

**dragenter/dragleave gotcha:** The `dragleave` event fires when the pointer moves over a child element inside the drop zone. The standard fix is to track enter/leave with a counter or use `relatedTarget` checks: [ASSUMED — documented browser event behavior]

```typescript
// [ASSUMED] Counter pattern for nested drag events
let dragCounter = 0

function onDragEnter(e: DragEvent) {
  e.preventDefault()
  dragCounter++
  setDragActive(true)
}
function onDragLeave(e: DragEvent) {
  dragCounter--
  if (dragCounter === 0) setDragActive(false)
}
function onDragOver(e: DragEvent) {
  e.preventDefault()  // required to enable drop
}
function onDrop(e: DragEvent) {
  e.preventDefault()
  dragCounter = 0
  setDragActive(false)
  const file = e.dataTransfer?.files[0]
  if (!file) return
  if (!file.name.endsWith('.zip')) {
    showError('Please drop a .zip file')
    return
  }
  void handleUpload(file)
}

// Mount on document.body in useEffect
document.body.addEventListener('dragenter', onDragEnter)
document.body.addEventListener('dragleave', onDragLeave)
document.body.addEventListener('dragover', onDragOver)
document.body.addEventListener('drop', onDrop)
```

### Context Menu Positioning

**Requirement (Claude's discretion):** Prevent viewport overflow.

```typescript
// [ASSUMED] Standard viewport-clamping for fixed context menus
interface ContextMenuPos { x: number; y: number }

function clampToViewport(
  clickX: number, clickY: number,
  menuW = 160, menuH = 96
): ContextMenuPos {
  return {
    x: Math.min(clickX, window.innerWidth - menuW - 8),
    y: Math.min(clickY, window.innerHeight - menuH - 8),
  }
}

// Usage in onContextMenu handler:
function onContextMenu(e: React.MouseEvent) {
  e.preventDefault()
  const pos = clampToViewport(e.clientX, e.clientY)
  setContextMenu({ open: true, x: pos.x, y: pos.y })
}
```

The context menu is rendered as `position: fixed; left: {x}px; top: {y}px`. Dismiss by click-outside via a document-level `mousedown` listener that checks if the click target is inside the menu element.

### URL Hash Extension (INT-04)

The existing `useHashSync` encodes only `race`, `driver`, `stint`. Phase 6 adds `pos` (current lap) to the hash so the exact view is restored.

```typescript
// Extended hash format:
// #race=2024_bahrain&driver=LEC&stint=1&lap=7
```

**Encoding `pos`:** Store `Math.floor(pos)` as an integer lap number. On restore, call `seek(lap)`. No need for float precision — the scrubber will be at that integer lap.

**Parameter overrides:** Per D-11 the URL encodes "any parameter overrides." Phase 5 did not implement parameter overrides (they are v2 scope per Deferred). For Phase 6, only `pos` (as `lap`) is added to the existing hash. The `useHashSync` hook is the right place to extend.

**URL length:** With only `race` (20 chars) + `driver` (3) + `stint` (1) + `lap` (2) the hash stays well under any URL limit. No base64 encoding needed. [ASSUMED — simple analysis of field lengths]

### Modal/Overlay Pattern (consistent across T, ?, ⓘ)

All overlays use the same structural pattern per CONTEXT.md canonical-refs:

```typescript
// [VERIFIED: codebase pattern — ErrorBoundary.tsx, LapPanel.tsx use same approach]
// position: fixed overlay with backdrop
{open && (
  <div
    style={{
      position: 'fixed', inset: 0, zIndex: 100,
      background: 'rgba(5,7,11,0.85)',
      backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}
    onClick={() => setOpen(false)}  // backdrop click dismisses
  >
    <div
      style={{
        background: 'var(--panel)',
        border: '1px solid var(--rule-strong)',
        // no border-radius — CLAUDE.md aesthetic rule
        padding: '24px 32px',
        fontFamily: 'var(--mono)',
        minWidth: 480,
      }}
      onClick={e => e.stopPropagation()}  // prevent backdrop dismiss
    >
      {/* content */}
    </div>
  </div>
)}
```

**T = MapPanel fullscreen:** The `MapPanel` component is rendered twice — once in the cockpit grid cell (always), and once inside the fullscreen overlay when `mapFullscreen === true`. The grid cell MapPanel remains visible underneath the backdrop. [VERIFIED: CONTEXT.md D-06]

### Toast Pattern

```typescript
// [ASSUMED] Minimal toast — no library
function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2000)
    return () => clearTimeout(t)
  }, [onDone])

  return (
    <div style={{
      position: 'fixed', top: 60, left: '50%', transform: 'translateX(-50%)',
      zIndex: 200,
      background: 'var(--panel)',
      border: '1px solid var(--accent)',
      color: 'var(--accent)',
      fontFamily: 'var(--mono)',
      fontSize: 11, fontWeight: 700, letterSpacing: 2,
      padding: '8px 20px',
    }}>
      {message}
    </div>
  )
}
```

The toast is rendered in `App.tsx` conditional on `useUIStore(s => s.toastMessage)` (add `toastMessage: string | null` and `showToast(msg: string)` to the store). `showToast` sets the message; the Toast component's `onDone` clears it.

### Scrubber Sector Coloring

The existing `Scrubber` renders a single rail. Sector coloring requires:

1. Read `sectorBounds: [number, number][]` from `useSimulationStore(s => s.data?.sectorBounds)`.
2. `sectorBounds` is an array of index pairs into `track[]` — it represents track geometry fraction, NOT lap numbers. For the scrubber (which is lap-indexed), derive lap boundaries from `maxLap` divided into thirds (S1: laps 1..floor(maxLap/3), S2: ..floor(2*maxLap/3), S3: ..maxLap). This is the same approximation used in LapPanel.tsx for sector cards. [VERIFIED: codebase read — LapPanel.tsx line 29-31]
3. If `sectorBounds` contains lap-indexed data (depends on backend implementation) use it directly; otherwise use the thirds approximation.

```typescript
// Three segment divs, absolutely positioned over the rail
const S_COLORS = ['#3a98b4', '#2a7a93', '#1d6278']  // from CONTEXT.md D-04

const sectors = [
  { start: 0, end: maxLap / 3 },
  { start: maxLap / 3, end: 2 * maxLap / 3 },
  { start: 2 * maxLap / 3, end: maxLap },
]

{sectors.map((s, i) => {
  const left = (s.start / maxLap) * 100
  const width = ((s.end - s.start) / maxLap) * 100
  return (
    <div key={i} style={{
      position: 'absolute',
      left: `${left}%`, width: `${width}%`,
      top: 10, height: 3,
      background: S_COLORS[i],
      opacity: 0.6,
    }} />
  )
})}
```

**Pit stop markers (D-04):** Derive from laps where `lap.stint_age === 0` after lap 1. These represent the start of a new stint. Check `LapData.stint_age` field:

```typescript
// [VERIFIED: codebase read — types.ts; LapData has stint_age: number]
const pitLaps = data?.laps
  .filter((l, i) => i > 0 && l.stint_age === 0)
  .map(l => l.lap_number) ?? []
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File download | Custom server endpoint or file write | `URL.createObjectURL` + `<a>.click()` | Browser API, no server needed |
| Upload progress | `fetch` with progress | `XMLHttpRequest` with `upload.progress` event | `fetch` streams have no upload progress in 2026 [ASSUMED] |
| Clipboard write | `document.execCommand('copy')` (deprecated) | `navigator.clipboard.writeText()` | Modern async API, no selection manipulation |
| SVG to raster | html2canvas, puppeteer, server-side | `XMLSerializer` + `<img>` + `<canvas>` | Works in-browser, no dependency, D-12 decision |
| Modal stacking | React Portal + library | `position: fixed` + `z-index` | Sufficient for one modal at a time; no library |
| Keyboard shortcut manager | `react-hotkeys-hook` or similar | `document.addEventListener('keydown')` | No dependency needed for ~12 shortcuts |
| D3 zoom sync | `d3.zoom()` attached to each SVG | Zustand `xZoom` state + manual wheel/drag handlers | Enables cross-component sync without `d3.zoom` transform propagation complexity |

**Key insight:** Every feature in Phase 6 can be implemented with browser-native APIs and existing dependencies. The only new install is `@playwright/test` for E2E tests.

---

## Common Pitfalls

### Pitfall 1: Stale Closure in Keyboard Handler

**What goes wrong:** Using hook values (`pos`, `speed`, `maxLap`) inside `document.addEventListener` in a `useEffect` with empty deps array causes the handler to capture stale values from mount time.
**Why it happens:** `useEffect(() => { ... }, [])` closes over the values at mount; subsequent store updates are invisible to the closed-over function.
**How to avoid:** Inside the handler, call `useUIStore.getState()` and `useSimulationStore.getState()` to get current values at call time. Never put store values in the closure.
**Warning signs:** Keyboard shortcuts work once then have no effect, or always jump to lap 1 regardless of current position.

### Pitfall 2: dragenter/dragleave Firing on Child Elements

**What goes wrong:** The drop overlay disappears when the user moves the mouse over any child element of `document.body` (because `dragleave` fires when leaving a child, before `dragenter` fires on the parent again).
**Why it happens:** Browser fires `dragleave` on the parent when pointer enters a child, even if still within the drag zone.
**How to avoid:** Use a `dragCounter` integer (increment on `dragenter`, decrement on `dragleave`, show overlay when > 0) or check `e.relatedTarget` is not inside the body.
**Warning signs:** Drop overlay flickers as user drags over the app.

### Pitfall 3: canvas.toBlob() Taint from Cross-Origin Images

**What goes wrong:** If any image element (SVG `<image>` tag, background, or external font) from a different origin is drawn to canvas, the canvas is "tainted" and `toBlob()` throws a `SecurityError`.
**Why it happens:** Browser security policy prevents reading pixel data from cross-origin images.
**How to avoid:** The PhysicsChart SVG uses only inline data (no `<image>` tags, no external resources). As long as no `<image>` elements reference external URLs, the canvas will not be tainted. Self-hosted fonts referenced via CSS `@font-face` do NOT taint the canvas when the SVG is serialized (fonts are loaded via CSS, not inline in SVG). [ASSUMED]
**Warning signs:** `canvas.toBlob is not a function` or `SecurityError: The operation is insecure`.

### Pitfall 4: Speed Type Union Breaking TypeScript

**What goes wrong:** The existing `useUIStore` types `speed` as `1 | 2 | 4 | 8`. The `setSpeed` calls in `TopStrip.tsx` iterate over `[1, 2, 4, 8] as const`. Changing to `0.5 | 1 | 2 | 4` requires updating the type union, the button array, and the RAF arithmetic check (only if 0.5 causes issues).
**Why it happens:** TypeScript literal union types.
**How to avoid:** Update all three locations atomically: type in `useUIStore.ts`, button array in `TopStrip.tsx`, and add `0.5` to the valid values. The RAF arithmetic `dt * speed / LAP_SECONDS` works correctly with `0.5` since it is standard floating-point multiplication.
**Warning signs:** TypeScript error `Argument of type '0.5' is not assignable to parameter of type '1 | 2 | 4 | 8'`.

### Pitfall 5: Context Menu Not Dismissed on Scroll or Window Resize

**What goes wrong:** The context menu appears at a fixed position; if the user scrolls or resizes the window, the menu is now mispositioned and no longer dismisses properly.
**Why it happens:** `position: fixed` menus do not move with content but remain attached to viewport coordinates.
**How to avoid:** Add `scroll` and `resize` event listeners that dismiss the menu (set `contextMenu.open = false`). The simplest approach: add a `mousedown` listener on `document` that fires any time the user clicks (including on the menu backdrop) and closes the menu unless the click target is inside the menu element.
**Warning signs:** Menu persists after user scrolls the PhysicsPanel.

### Pitfall 6: PhysicsPanel Export Capturing Only One Chart

**What goes wrong:** The `onContextMenu` is placed on a single `PhysicsChart` div. When exporting "all 4 corners" (D-11), only the one chart's SVG is serialized.
**Why it happens:** Each `PhysicsChart` owns one `<svg>` element; D-11 requires all 4.
**How to avoid:** Place the `onContextMenu` handler on the `PhysicsPanel` container (the `role="tabpanel"` div). The export function queries all `<svg>` children and either: (a) combines them into a single tall SVG, or (b) exports each as a separate file. Approach (a) is preferred for a clean single export.
**Warning signs:** Export only shows 1 of 4 corner charts.

### Pitfall 7: wheel event passive listener blocking preventDefault

**What goes wrong:** `onWheel` on a React element uses passive listeners by default in some browsers, causing `e.preventDefault()` to throw a console error and not prevent page scroll.
**Why it happens:** Chrome 56+ added passive event listeners for touch and wheel events to improve scroll performance. React's synthetic event system honors this.
**How to avoid:** Attach the wheel listener via `addEventListener('wheel', handler, { passive: false })` in a `useEffect` on the chart's `ref`, not via `onWheel` JSX prop. [ASSUMED — documented browser behavior]
**Warning signs:** Console warning "Unable to preventDefault inside passive event listener"; page scrolls while zooming chart.

### Pitfall 8: Playwright Test Isolation — Store State Bleeds Between Tests

**What goes wrong:** Zustand store state from one test persists into the next because the module is imported once and the store singleton is shared.
**Why it happens:** Jest/Vitest and Playwright run in the same Node process (for unit tests) or the same page context (for E2E). Zustand stores are module-level singletons.
**How to avoid:** For Playwright E2E tests, each test navigates to a fresh URL, which resets the page entirely — no store bleed. For Vitest unit tests, call the store's `reset()` action (already exists in `useSimulationStore`) in `beforeEach`.
**Warning signs:** Tests pass individually but fail when run together.

---

## Code Examples

### Verified Patterns from Codebase

### Complete speed type fix
```typescript
// Source: [VERIFIED: codebase read — useUIStore.ts line 17]
// BEFORE: speed: 1 | 2 | 4 | 8
// AFTER:
speed: 0.5 | 1 | 2 | 4
setSpeed: (speed: 0.5 | 1 | 2 | 4) => void

// TopStrip.tsx button array fix:
{([0.5, 1, 2, 4] as const).map(s => (
  <button key={s} onClick={() => setSpeed(s)} style={{
    padding: '4px 8px',
    background: speed === s ? 'var(--rule-strong)' : 'transparent',
    // ...
  }}>
    {s}×
  </button>
))}
```

### Step buttons in TopStrip MIDDLE BLOCK
```typescript
// [ASSUMED] Unicode button chars per CONTEXT.md specifics section
const seek = useUIStore(s => s.seek)
const maxLap = useSimulationStore(s => s.data?.laps.length ?? 22)
const pos = useUIStore(s => s.pos)

// Insert before play/pause button:
<button onClick={() => seek(1)} title="Jump to first lap" style={btnStyle}>⏮</button>
<button onClick={() => seek(Math.max(1, Math.floor(pos) - 1))} title="Step back 1 lap" style={btnStyle}>◄</button>
// [existing play/pause button]
<button onClick={() => seek(Math.min(maxLap, Math.floor(pos) + 1))} title="Step forward 1 lap" style={btnStyle}>►</button>
<button onClick={() => seek(maxLap)} title="Jump to last lap" style={btnStyle}>⏭</button>
```

### StatusLog collapse driven by Zustand
```typescript
// [VERIFIED: codebase read — StatusLog.tsx uses local useState; must change to Zustand]
// StatusLog.tsx: replace local state with store:
const statusLogCollapsed = useUIStore(s => s.statusLogCollapsed)
const toggleStatusLog = useUIStore(s => s.toggleStatusLog)
// Remove: const [collapsed, setCollapsed] = useState(false)
// Replace handler: onClick={() => toggleStatusLog()}
```

### MSW handler for /sessions/upload mock
```typescript
// Source: [VERIFIED: codebase read — mocks/handlers.ts pattern]
http.post('/api/sessions/upload', async () => {
  // Simulate upload processing delay
  await new Promise(r => setTimeout(r, 100))
  return HttpResponse.json({ session_id: 'test-session-abc123' })
}),
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | All frontend tooling | Yes | 24.14.1 | — |
| npm | Package management | Yes | bundled with Node | — |
| @playwright/test | D-23 E2E tests | No (not installed) | 1.59.1 in registry | Must install |
| Chromium browser | Playwright tests | Partial — `npx playwright` binary is v1.59.1 but browser not installed | Install with `npx playwright install chromium` | — |
| navigator.clipboard API | D-08, D-15 | Yes (HTTPS required; localhost also works) | Browser native | Must serve on HTTPS in production |
| XMLHttpRequest | D-17 upload progress | Yes | Browser native | — |
| XMLSerializer | D-12, D-13 SVG export | Yes | Browser native | — |
| Canvas API | D-12 PNG export | Yes | Browser native | — |

**Missing dependencies:**
- `@playwright/test` + Chromium binary: must be installed in Wave 0 of Phase 6 plan. Command: `cd frontend && npm install --save-dev @playwright/test && npx playwright install chromium`.

**`navigator.clipboard` in non-HTTPS:** In development (Vite dev server on `http://localhost`), `navigator.clipboard` is available because `localhost` is treated as a secure context. In production (Vercel, HTTPS) it will also work. No fallback needed for this project's deployment target. [ASSUMED]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 2.1.9 (unit) + Playwright 1.59.1 (E2E) |
| Config file | `frontend/vitest.config.ts` (exists); `frontend/playwright.config.ts` (Wave 0 gap) |
| Quick run command | `cd frontend && npm test` (Vitest unit only) |
| Full suite command | `cd frontend && npm test && npx playwright test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAY-01 | Speed buttons render 0.5×/1×/2×/4× | unit | `npm test -- useUIStore` | Partial (useUIStore.test.ts exists, needs speed update) |
| PLAY-01 | seek clamps to [1, maxLap] | unit | `npm test -- useUIStore` | Partial |
| PLAY-02 | RAF loop uses 0.5× speed correctly | unit | `npm test -- App` | No — Wave 0 |
| INT-01 | Space key toggles playing | E2E | `npx playwright test keyboard` | No — Wave 0 |
| INT-01 | Arrow keys step lap | E2E | `npx playwright test keyboard` | No — Wave 0 |
| INT-01 | Esc closes modal | E2E | `npx playwright test keyboard` | No — Wave 0 |
| INT-02 | Right-click opens context menu | E2E | `npx playwright test export` | No — Wave 0 |
| INT-02 | Export PNG triggers download | E2E | `npx playwright test export` | No — Wave 0 |
| INT-02 | Export CSV has correct columns | unit | `npm test -- exportCsv` | No — Wave 0 |
| INT-03 | Right-click tire writes to clipboard | E2E | `npx playwright test tire-copy` | No — Wave 0 |
| INT-04 | URL hash includes lap; reload restores | E2E | `npx playwright test hash` | No — Wave 0 |
| INT-05 | Drop zip → POST /sessions/upload | E2E | `npx playwright test upload` | No — Wave 0 |
| INT-05 | XHR upload progress updates UI | unit | `npm test -- useDragUpload` | No — Wave 0 |
| INT-06 | Provenance modal renders fastf1_version | unit | `npm test -- ProvenanceModal` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `cd frontend && npm test` (Vitest, < 10s)
- **Per wave merge:** `cd frontend && npm test && npx playwright test` (full suite)
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps

- [ ] `frontend/playwright.config.ts` — Playwright configuration (baseURL, webServer, project)
- [ ] `frontend/tests/keyboard.spec.ts` — keyboard shortcut E2E tests
- [ ] `frontend/tests/export.spec.ts` — chart export E2E tests
- [ ] `frontend/tests/hash.spec.ts` — URL hash round-trip E2E
- [ ] `frontend/tests/upload.spec.ts` — drag-and-drop upload E2E
- [ ] `frontend/src/lib/export.ts` — export utilities (unit-testable)
- [ ] `frontend/src/hooks/useDragUpload.ts` — upload hook (unit-testable)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth in v1 |
| V3 Session Management | Partial | `session_id` is ephemeral per-upload, no persistent auth token |
| V4 Access Control | No | Public read-only app |
| V5 Input Validation | Yes | ZIP file validation: extension check + MIME type check; backend already guards against Zip Slip + decompression bombs (Phase 4) |
| V6 Cryptography | No | No crypto in frontend |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious ZIP upload (Zip Slip, symlinks) | Tampering | Backend already implements Zip Slip + symlink + decompression bomb guards (Phase 4, verified in ROADMAP) |
| SVG XSS via export | Tampering | The SVG is generated entirely from `data.laps` numeric values, never from user-supplied strings. No `innerHTML` injection path. |
| Clipboard API phishing (copying malicious URL) | Spoofing | The clipboard write is `window.location.href` — cannot be manipulated by the app beyond what the user already sees in the address bar. |
| Context menu click-jacking | Spoofing | No external content in the context menu; all items are hardcoded strings. |
| XHR CSRF on upload | Tampering | The `/sessions/upload` endpoint uses multipart/form-data; CSRF token not required for same-origin requests. Vite proxy (`/api` → `localhost:8000`) keeps requests same-origin in dev. CORS is locked in Phase 7. |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `document.execCommand('copy')` | `navigator.clipboard.writeText()` | ~2019 | Async, no selection hack needed |
| `odeint` for SSE | Fetch + ReadableStream | Phase 5 | Already in use in this project |
| `d3.zoom()` with `zoom.transform` | Manual wheel/drag with shared state | 2024+ (React context) | Simpler sync across components |
| `html2canvas` | XMLSerializer + canvas | ~2022 | No dependency, no CORS issues |

**Deprecated/outdated:**
- `document.execCommand('copy')`: deprecated in all major browsers; `navigator.clipboard` is the standard.
- `d3.zoom` with `zoom.on('zoom', ...)` applied to each SVG independently: works but requires `zoom.transform` to sync — the shared Zustand domain is simpler for this use case.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `fetch` does not expose upload progress in 2026 | Don't Hand-Roll, useDragUpload | If Fetch Streams API adds upload progress, XHR could be replaced with fetch; low risk, XHR still works |
| A2 | `navigator.clipboard` available on localhost without HTTPS | Environment Availability | If not available in dev, fallback to `document.execCommand('copy')` (deprecated but still functional) |
| A3 | Canvas is not tainted by self-hosted fonts in inline SVG | Pitfall 3 | If tainted, must embed font as base64 data URL in SVG `<defs>` |
| A4 | Stale closure pattern: `useUIStore.getState()` in keydown handler is correct | Keyboard Shortcuts | If Zustand changes `.getState()` API (extremely unlikely in 5.x), alternative is adding store values to `useEffect` deps array and using `useCallback` |
| A5 | `wheel` event passive listener prevents `preventDefault` in React JSX `onWheel` | Pitfall 7 | If React 19 changed passive defaults, `onWheel` may work; test during implementation |
| A6 | `sectorBounds` in simulation result represents track geometry indices, not lap numbers | Scrubber sector coloring | If it contains lap indices, the thirds approximation is unnecessary; safe to keep thirds as fallback |
| A7 | String-replace approach for CSS var substitution in SVG is reliable | SVG Export | Computed style traversal is the fallback; both approaches produce correct colors for the token set |
| A8 | Playwright 1.59.1 (currently in registry) is compatible with the installed Node 24.14.1 | Environment Availability | Verified: node 24 + playwright 1.59 is a supported combination [ASSUMED from version ranges] |

---

## Open Questions

1. **Does `sectorBounds` carry lap indices or track-geometry indices?**
   - What we know: `sectorBounds: [number, number][]` in `SimulationResult` per `types.ts`; populated from `raw.sector_bounds` in the SSE response mapper.
   - What's unclear: The backend implementation (Phase 4/5) may return track-geometry fractions or lap-numbered boundaries — the field name does not disambiguate.
   - Recommendation: Implement scrubber sector coloring with the thirds-of-maxLap approximation as the default and add a code comment to switch to direct `sectorBounds` data if the backend provides lap indices. No blocking issue.

2. **Does the MSW mock for `/sessions/upload` need a multipart-aware response?**
   - What we know: MSW 2.x handlers can inspect `FormData` body.
   - What's unclear: The Playwright E2E tests will exercise this mock (or a real backend).
   - Recommendation: Add a simple MSW handler that returns `{ session_id: 'test-session-abc123' }` without inspecting the body. Playwright tests should target the real backend (Vite proxy to localhost:8000) or a dedicated mock.

3. **Shift+←/→ sector jump: lap-count thirds or sectorBounds?**
   - Same ambiguity as Q1. Use thirds of `maxLap` as default (consistent with LapPanel sector cards).

---

## Sources

### Primary (HIGH confidence)
- `[VERIFIED: codebase read]` — `useUIStore.ts`, `useSimulationStore.ts`, `App.tsx`, `TopStrip.tsx`, `Scrubber.tsx`, `PhysicsChart.tsx`, `PhysicsPanel.tsx`, `CarWheel.tsx`, `sse.ts`, `useHashSync.ts`, `StatusLog.tsx`, `LapPanel.tsx`, `types.ts`, `package.json`, `vitest.config.ts` — all read directly during this session
- `[VERIFIED: CONTEXT.md]` — all 23 implementation decisions (D-01 through D-23), deferred items, and discretion areas
- `[VERIFIED: CLAUDE.md]` — design lock tokens, typography, aesthetic rules, stack decisions
- `[VERIFIED: npm registry via node]` — `@playwright/test` version 1.59.1 current; Node 24.14.1 installed

### Secondary (MEDIUM confidence)
- Browser specification: `navigator.clipboard.writeText()` — W3C Clipboard API Level 1; widely documented
- Browser specification: `XMLSerializer.serializeToString()` — DOM Living Standard
- Browser specification: `HTMLCanvasElement.toBlob()` — HTML Living Standard
- Browser specification: `XMLHttpRequest.upload.progress` — XMLHttpRequest Level 2

### Tertiary (LOW confidence — verify during implementation)
- Passive wheel event behavior in React 19 (A5 assumption)
- Canvas taint behavior with self-hosted fonts (A3 assumption)
- `useUIStore.getState()` stale closure prevention pattern (A4 — standard Zustand pattern but not verified against v5.0.12 docs this session)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified from `package.json` in codebase
- Architecture patterns: HIGH for store/event patterns (verified codebase), MEDIUM for export/drag patterns (assumed, standard browser APIs)
- Pitfalls: HIGH for store/closure pitfalls (verified codebase), MEDIUM for browser event edge cases (assumed)

**Research date:** 2026-04-25
**Valid until:** 2026-07-25 (stable APIs; Playwright minor versions may update)
