# Phase 6: Playback, Interactions & Sharing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 06-playback-interactions-sharing
**Areas discussed:** Transport bar controls, Keyboard shortcut behaviors, Chart export mechanism, Drag-and-drop upload + provenance

---

## Transport Bar Controls

| Option | Description | Selected |
|--------|-------------|----------|
| Stay in TopStrip | Add step/jump buttons next to play/pause; sector-color existing Scrubber; no layout change | ✓ |
| Add a bottom transport bar | New 48px row below cockpit grid; moves all playback controls there | |

**User's choice:** Stay in TopStrip
**Notes:** Design lock `grid-template-rows: 52px 1fr` is preserved. Phase 5 already put play/pause + scrubber in TopStrip so this is consistent.

---

## Keyboard Shortcut Behaviors

### T / E toggles

| Option | Description | Selected |
|--------|-------------|----------|
| T = expand MapPanel fullscreen | Overlay at ~80% viewport; E collapses StatusLog height | ✓ |
| T = hide/show MapPanel in grid | Removes MapPanel cell; PhysicsPanel takes full right column | |

**User's choice:** T = fullscreen overlay, E = collapse StatusLog

### S / ? behavior

| Option | Description | Selected |
|--------|-------------|----------|
| S = copy URL + flash toast | navigator.clipboard + 2s toast; ? = shortcuts modal | ✓ |
| S = open share dialog | Modal with URL pre-selected; ? = same shortcuts modal | |

**User's choice:** S = clipboard copy + toast; ? = shortcuts modal

---

## Chart Export Mechanism

### Export trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Right-click context menu | Custom overlay with Export PNG / SVG / CSV; onContextMenu preventDefault | ✓ |
| Hover reveals export button | Icon appears top-right on hover; dropdown opens | |

**User's choice:** Right-click context menu

### Export scope

| Option | Description | Selected |
|--------|-------------|----------|
| Current metric, all 4 corners | Full 4-chart panel export; CSV = all laps × 4 corners | ✓ |
| Single corner only | Export just the right-clicked chart | |

**User's choice:** All 4 corners for current metric

---

## Drag-and-drop Upload + Provenance

### Tire widget clipboard format

| Option | Description | Selected |
|--------|-------------|----------|
| Formatted monospace string | "FL \| 94.2°C \| Grip 1.31μ \| Wear 3.2 MJ \| Slip 2.1°" | ✓ |
| JSON object | `{"corner":"FL","temp":94.2,...}` | |

**User's choice:** Formatted monospace string

### Drop zone coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Full app overlay | Drag over anything → dim cockpit + centered drop zone | ✓ |
| Dedicated upload zone in TopStrip | Small drag-here icon; only active on hover over that area | |

**User's choice:** Full app overlay with auto-simulate on drop

### Provenance footer placement

| Option | Description | Selected |
|--------|-------------|----------|
| ⓘ info button → modal | Small ⓘ in TopStrip right block; modal on click | ✓ |
| Inline in TopStrip | Tiny text always visible in right block | |

**User's choice:** ⓘ info button → modal

---

## Claude's Discretion

- Toast implementation (no library)
- Exact step/jump button sizing in TopStrip
- Sector color boundaries on Scrubber
- StatusLog collapse animation duration
- xZoom reset behavior on new simulation load
- Context menu overflow handling

## Deferred Ideas

- Intra-lap 4Hz car animation → v2
- Three.js 3D track map → v2
- What-If sliders / compound comparison → v2
