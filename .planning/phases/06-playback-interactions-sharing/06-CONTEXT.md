# Phase 6: Playback, Interactions & Sharing - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 completes the interactive layer on top of the Phase 5 visualization substrate. A user can step through laps with keyboard or buttons, export any chart, copy tire metrics, drop in a FastF1 cache zip for a custom session, and share a URL that restores their exact view — all within the same cockpit layout.

Phase 6 does NOT include: backend physics changes, new visualization panel types, Three.js 3D map, What-If sliders, compound comparison, or deployment (Phase 7).

**Phase 5 carry-ins that must be resolved in Phase 6:**
- SC-3: `useSimulationStore.error` is set on SSE failure but nothing reads it. Add error banner + retry button to TopStrip.
- SC-4: Mouse-wheel zoom / drag-to-pan on PhysicsPanel shared x-axis. Implement in Phase 6.
- Playwright E2E tests deferred from Phase 5.

</domain>

<decisions>
## Implementation Decisions

### A — Transport Bar & Step Controls

- **D-01:** All playback controls stay in the **TopStrip** — no new layout row. The locked design `grid-template-rows: 52px 1fr` is preserved. Phase 6 adds `⏮ ◄ ► ⏭` step/jump buttons to the TopStrip's MIDDLE BLOCK next to the existing play/pause button.
- **D-02:** Step ±1 lap maps to `seek(pos ± 1)` clamped to `[1, maxLap]`. Jump first/last maps to `seek(1)` / `seek(maxLap)`.
- **D-03:** Speed options extended to include **0.5×** (the ROADMAP specifies 0.5×/1×/2×/4×; Phase 5 shipped 1×/2×/4×/8×). Add 0.5× and confirm the final set is 0.5×/1×/2×/4×. Remove 8× unless user requests it.
- **D-04:** The existing `Scrubber` is upgraded to show **sector-colored segments**. Each lap range maps to S1/S2/S3 color (`#3a98b4` / `#2a7a93` / `#1d6278` from MapPanel). Pit-stop lap markers are shown as white tick marks at the exact lap index where `stint_age === 0` on a subsequent stint (derived from simulation metadata when available; omitted if not present in the result).

### B — Keyboard Shortcuts

- **D-05:** Global `keydown` listener mounted in `App.tsx`. All shortcuts work when no input is focused. Shortcuts:

  | Key | Action |
  |-----|--------|
  | Space | Play / Pause |
  | ← / → | Step −1 / +1 lap |
  | Shift+← / Shift+→ | Jump to start of current sector / next sector |
  | Home / End | Jump to lap 1 / last lap |
  | 1 / 2 / 3 / 4 | Focus FL / FR / RL / RR corner (sets `hoveredCorner`) |
  | T | Toggle MapPanel fullscreen overlay |
  | E | Toggle StatusLog collapsed/expanded in LapPanel |
  | S | Copy current URL to clipboard + show toast |
  | ? | Open keyboard shortcuts modal |
  | Esc | Close any open modal/overlay (fullscreen map, shortcuts modal) |

- **D-06: T = MapPanel fullscreen overlay.** Pressing T renders MapPanel at ~80% viewport as a centered overlay (`position: fixed`, `z-index: 100`, backdrop blur). The overlay is dismissed by pressing T again or Esc. This does not change the cockpit grid — the MapPanel cell in the grid remains rendered underneath.

- **D-07: E = collapse StatusLog.** The `StatusLog` component in LapPanel gains a `collapsed` boolean prop driven by Zustand `useUIStore`. When collapsed, the StatusLog row height animates to 0 (CSS transition on `max-height`). E toggles this state.

- **D-08: S = copy URL to clipboard + toast.** No modal. `navigator.clipboard.writeText(window.location.href)` then shows a `position: fixed` toast at the top of the screen: `URL COPIED` in `var(--accent)` for 2 seconds. No library needed.

- **D-09: ? = shortcuts modal.** A centered modal overlay listing all shortcuts in a two-column monospace table. Uses the same backdrop pattern as the T fullscreen overlay. Dismissed by Esc or clicking the backdrop.

### C — Chart Export

- **D-10:** Right-clicking any `PhysicsChart` (or its containing `PhysicsPanel`) shows a **custom context menu overlay** — not the native browser context menu (which can't be reliably intercepted). The overlay is a small dark panel (`var(--panel)` background, `var(--rule)` border) with three items: "Export PNG", "Export SVG", "Export CSV". Clicking outside or pressing Esc dismisses it. `onContextMenu` → `e.preventDefault()` → show overlay.

- **D-11: Export scope = current metric tab, all 4 corners.** PNG and SVG capture the full 4-chart column (all four FL/FR/RL/RR charts stacked for the active metric). CSV exports all 22 laps × 4 corners for that metric with columns: `lap,fl_mean,fl_lo95,fl_hi95,fr_mean,...`.

- **D-12: PNG export implementation.** Use `foreignObject`-free SVG-to-canvas approach: serialize the SVG to a string, create a `<img>` with `src=data:image/svg+xml,...`, draw onto a `<canvas>`, then `canvas.toBlob()` → download. No html2canvas dependency.

- **D-13: SVG export.** Clone the SVG element, inline computed styles for `font-family` and `fill`, and trigger a download as `.svg`. No dependency.

- **D-14: CSV export.** Build the string in-memory from `data.laps` for the active metric. Trigger download via `URL.createObjectURL(new Blob([csv], {type:'text/csv'}))`.

- **D-15: Tire widget clipboard copy.** Right-clicking a `CarWheel` or `CarFooter` corner cell copies a formatted monospace string: `"FL | 94.2°C | Grip 1.31μ | Wear 3.2 MJ | Slip 2.1°"`. Uses `navigator.clipboard.writeText()`. Shows the same toast pattern as S (D-08).

### D — Drag-and-Drop Session Upload

- **D-16:** Dragging any file over the app window triggers a **full-app drop overlay** — the entire cockpit is dimmed with a centered `"DROP FASTF1 CACHE ZIP HERE"` message and a dashed accent border. This is achieved with a global `dragenter` / `dragleave` / `drop` listener on `document.body` in a `useDragUpload` hook.

- **D-17:** On drop, validate the file is a `.zip`. If not, show an error toast. If valid, `POST /sessions/upload` with `multipart/form-data`. Progress is shown as a progress bar in the overlay (using `XMLHttpRequest` `progress` event, since `fetch` does not expose upload progress). On success, the response includes a `session_id`; store this in `useSimulationStore` and auto-trigger `/simulate` with the new session. On error, show an error banner (same pattern as SC-3 carry-in).

- **D-18:** The backend `/sessions/upload` endpoint is already implemented in Phase 4. The frontend just needs the hook and overlay UI.

### E — Provenance Footer

- **D-19:** A small **ⓘ button** is added to the TopStrip right block (after the lap counter). Clicking it opens a centered modal with a monospace table of provenance fields: FastF1 version, model schema version, calibration ID, calibration date, run ID, and the disclaimer: `"Unofficial fan tool — not affiliated with F1, FIA, or Pirelli."` Modal dismissed by Esc or clicking backdrop.

- **D-20:** Provenance data is sourced from `data.meta` (`fastf1_version`, `model_schema_version`, `calibration_id`, `run_id`). Calibration date is not in the current meta schema — show "N/A" or omit if not present.

### F — Error/Retry UI (SC-3 carry-in from Phase 5)

- **D-21:** A dismissable error banner is added to the TopStrip. It reads `useSimulationStore(s => s.error)`. When non-null, it shows a red bar below the TopStrip with the error message and a "RETRY" button that re-runs the last `runSimulationStream` call. The banner is dismissed automatically on next successful run.

### G — PhysicsPanel Zoom/Pan (SC-4 carry-in from Phase 5)

- **D-22:** Mouse-wheel zoom and drag-to-pan on PhysicsPanel's shared x-axis. Implemented via a shared `xZoom` state in `useUIStore` (domain `[startLap, endLap]`). All four `PhysicsChart` components read `xZoom` and pass it as the D3 scale domain. Wheel event on any chart updates `xZoom`. Drag on any chart pans it. A "reset zoom" button appears when zoomed.

### H — Testing

- **D-23:** Playwright E2E tests (deferred from Phase 5) land in Phase 6. Critical paths to cover: (1) pick stint → run → panels populate, (2) keyboard shortcuts advance playback, (3) export downloads a file, (4) URL hash round-trip.

### Claude's Discretion

- Exact pixel placement and sizing of step/jump buttons in TopStrip
- Toast implementation (no library — a simple `position: fixed` div with a `setTimeout` unmount)
- Sector color boundaries on Scrubber derived from `sectorBounds` in simulation result
- CSS `max-height` transition duration for StatusLog collapse animation
- Whether `xZoom` resets on new simulation load (yes — reset to full range on `setData`)
- Context menu positioning (ensure it doesn't overflow viewport edges)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Layout & Design Contract
- `CLAUDE.md` §Design Lock — locked `grid-template-rows: 52px 1fr`, all 17 CSS tokens, typography; no changes to these
- `.planning/phases/05-dashboard-shell-visualization/05-CONTEXT.md` — D-04: hover is lap-discrete; intra-lap 4Hz animation deferred to Phase 6

### Phase 6 Requirements
- `.planning/ROADMAP.md` §Phase 6 — 7 success criteria; use as acceptance checklist

### Existing Phase 5 Code (extend, don't rewrite)
- `frontend/src/stores/useUIStore.ts` — `pos`, `playing`, `speed`, `mode`, `hoveredCorner`; Phase 6 adds `statusLogCollapsed`, `xZoom`, `mapFullscreen`
- `frontend/src/components/TopStrip/Scrubber.tsx` — upgrade sector coloring onto this component
- `frontend/src/components/TopStrip/TopStrip.tsx` — add step/jump buttons, ⓘ button, error banner here
- `frontend/src/components/PhysicsPanel/PhysicsChart.tsx` — add right-click context menu and zoom/pan here
- `frontend/src/components/CarPanel/CarWheel.tsx` — add right-click clipboard copy here
- `frontend/src/lib/sse.ts` — `runSimulationStream` re-used for retry flow (D-21)
- `frontend/src/App.tsx` — global `keydown` listener and drag-and-drop hook mounted here

### Backend Upload Endpoint
- `packages/api/src/f1_api/routers/` — `/sessions/upload` endpoint already implemented in Phase 4; frontend just calls it

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useUIStore` — already has `seek`, `togglePlaying`, `setSpeed`, `setHoveredCorner`; Phase 6 adds `statusLogCollapsed`, `xZoom`, `mapFullscreen`
- `Scrubber` — already has per-lap tick marks and pointer drag; needs sector color segments added
- `TopStrip` — already has MIDDLE BLOCK for playback controls; step/jump buttons slot in next to play/pause
- `PhysicsChart` — already has `onContextMenu` placeholder; needs custom menu overlay wired in
- `ErrorBoundary` — already wraps each panel; error banner in TopStrip is a separate concern (stream errors, not render crashes)

### Established Patterns
- All overlays use `position: fixed`, dark panel background (`var(--panel)`), backdrop click to dismiss, Esc to close — use this consistently for fullscreen map, shortcuts modal, provenance modal
- Zustand `useShallow` for multi-field selectors (already used in App.tsx and PhysicsChart.tsx)
- Toast pattern: `position: fixed`, top of screen, `var(--accent)` color, `setTimeout` unmount — no library

### Integration Points
- `useSimulationStore.data.sectorBounds` → Scrubber sector colors
- `useSimulationStore.error` → TopStrip error banner (SC-3 carry-in)
- `useSimulationStore.data.meta` → provenance modal fields
- `window.location.href` / `useHashSync` → S shortcut URL copy
- `document.body` dragenter/dragleave/drop → `useDragUpload` hook

</code_context>

<specifics>
## Specific Ideas

- **Step button icons:** Use Unicode `⏮ ◄ ► ⏭` (or ASCII `|< < > >|`) inline in the TopStrip buttons — no icon library needed, consistent with the monospace aesthetic.
- **Sector scrubber segments:** Divide the scrubber rail into 3 colored segments using the same sector colors as MapPanel (`#3a98b4`, `#2a7a93`, `#1d6278`). Each segment's width is proportional to its lap count fraction.
- **Fullscreen map overlay:** Use the existing MapPanel component directly inside a `position: fixed` container — no separate component needed. Add a close button top-right (`✕`) and listen for T/Esc.
- **Zoom reset button:** Appears in the PhysicsPanel tab strip as a small "↺ RESET" button when `xZoom` is not at full range.

</specifics>

<deferred>
## Deferred Ideas

- **Intra-lap 4Hz continuous animation** (car position at 4Hz during playback) — deferred to v2; Phase 6 playback advances lap-by-lap.
- **Three.js 3D track map** — v2 scope per CLAUDE.md.
- **What-If sliders and compound comparison** — v2 scope per PROJECT.md.
- **SSE/sync endpoint unification** — both endpoints coexist in v1.

</deferred>

---

*Phase: 06-playback-interactions-sharing*
*Context gathered: 2026-04-25*
