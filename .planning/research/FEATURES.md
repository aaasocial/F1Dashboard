# Features Research — F1 Tire Degradation Analyzer

**Scope:** V1 Stint Analyzer only. V2 features (pit optimizer, what-if lab, compound comparison, sensitivity explorer, driver comparison, educational overlay) are scoped out per PROJECT.md.
**Researched:** 2026-04-23
**Confidence:** MEDIUM-HIGH (UX patterns are well-established; motorsport-specific conventions drawn from adjacent tools, not first-party team tooling)

---

## Table Stakes (V1 must-haves)

These are features where absence makes users bounce. They exist across every serious analyst tool in the category (FastF1 community tools, TracingInsights, F1Tempo, general scientific dashboards).

| Feature | Complexity | User expectation source |
|---|---|---|
| **Race / driver / stint picker as primary entry point** | Low | Every F1 analysis tool (TracingInsights, F1Tempo, FastF1 community dashboards) opens on a selection UI. Users expect dropdowns with season → round → driver → stint cascade. |
| **Loading skeleton on initial paint (not spinner)** | Low | NN/g: skeleton screens reduce perceived wait ~40% vs spinners. Required because the dashboard has 6+ zones that load at different times (race list → driver list → telemetry fetch → simulation). |
| **Simulation progress indicator with phase labels** | Medium | <4s tasks = spinner per Carbon/PatternFly, but the 2–3s physics run crosses seven modules. Users tolerate longer waits when they see *what* is happening ("Fetching telemetry… running thermal ODE… computing confidence intervals"). Without phase text, 3s feels broken. |
| **Error states with recovery action** | Low | Mandatory. FastF1 calls can fail (cache miss, session not yet released, rate limit). "Try again" button + human-readable cause. Silent failure is the #1 bounce driver for data tools. |
| **Data provenance / freshness indicator** | Low | "Telemetry cached 2h ago · FastF1 v3.x · Model v1.0 · Calibration tag 2026-Q1". Users who will cite this in articles/fantasy leagues *must* be able to verify the data source and model version. Required for credibility. |
| **Lap-by-lap multi-line chart (lap time, sliding power, tread temp) with shared X-axis** | Medium | The canonical F1 analyst chart. TracingInsights, F1Tempo, and every FastF1 tutorial notebook use this exact layout. Shared X + linked hover is table stakes, not a differentiator. |
| **Linked brushing / hover across all charts + track map + tire array** | High | Required per PROJECT.md Zone 4. Observable and D3-foresight establish the pattern; users of TracingInsights expect "hover one chart → see the timepoint on all charts and the track map." Without it, the dashboard feels fragmented. |
| **Compound colour coding (SOFT=red, MEDIUM=yellow, HARD=white)** | Low | FIA-standard. Any deviation will confuse F1 fans immediately. Use the broadcast palette. |
| **Transport bar: play/pause, step, scrub, speed** | Medium | Already in spec (Zone 6). Standard video-player affordance. Users expect spacebar=play, arrows=step, scrub-by-drag. |
| **Pit stop markers on scrub bar** | Low | Essential context. Stint boundaries must be visible at-a-glance. |
| **Tooltip on hover showing exact values** | Low | Universal. Must include units (°C, MJ, %, deg). Without units the numbers are meaningless to non-experts. |
| **Confidence interval bands on prediction lines** | Medium | PROJECT.md mandates Bayesian CIs as first-class. Shaded area under/over line (d3.area before the line to avoid overlap) is the D3 idiom. Toggle to hide is nice-to-have. |
| **Keyboard shortcuts (Space, ←/→, Shift+←/→, Home/End, 1–4, ?, Esc)** | Low | Already in spec. Professional analyst tools (CRM Analytics, Informatica Analyst) all expose keyboard nav. Include `?` to show shortcut cheatsheet overlay — that is the ubiquitous convention. |
| **Export chart as PNG + SVG + CSV (right-click)** | Medium | PNG for Twitter/blog, SVG for publication-quality articles, CSV for re-analysis in pandas/Excel. This is the universal trio per AnyChart/Highcharts/amCharts. Omitting any one breaks a known use case. |
| **URL hash state encoding for shareable deep links** | Medium | Already in spec. Zustand v5 recommends URL-hash storage exactly for this. This replaces user accounts in v1 — must actually restore state faithfully on reload (race, driver, stint, current lap, which tire selected). |
| **Colorblind-safe palette beyond compound colors** | Low | ~8% of users have CVD. For non-compound data (temperature gradient, grip %, confidence bands), use Viridis (sequential) and Okabe-Ito (categorical). Never use red/green for good/bad. |
| **Dark theme (only, in V1)** | Low | Already in spec. Motorsport tooling convention. Light theme is a common request but deferrable — not a bounce-trigger. |
| **Responsive to tablet; view-only on mobile** | Medium | Already in spec. A mobile user should be able to *see* a shared URL, even if they can't drive it. A full-featured mobile UX is v2+. |
| **Empty state on first load (before any selection)** | Low | Don't show a blank dashboard. Show a hero prompt: "Pick a race to begin" + maybe 3 curated "try this stint" links (Monaco 2023 / VER, Silverstone 2024 / HAM, etc.). Carbon Design System "starter content" pattern. |

---

## Differentiators (V1 competitive advantages)

Features that set this tool apart from FastF1 notebooks, TracingInsights, and F1Tempo. Keep these; they justify the project's existence.

| Feature | Why it's differentiating |
|---|---|
| **Physics-based predictions with confidence intervals (not just observed telemetry)** | No public tool does this today. TracingInsights/F1Tempo replay what happened; this tool explains *why* it degraded — with quantified uncertainty. The core value prop. |
| **Four-tire 2×2 widget array with live temp/grip/energy/slip** | Broadcast-grade visualization that even F1TV doesn't offer publicly for historical races. Visceral, scannable, teach-by-looking. |
| **Animated playback with linked track position** | F1Tempo is lap-table-centric; TracingInsights is chart-centric. Sync'd 2D track + tire array + charts on a single timeline is the differentiator — it feels like mission control, not a spreadsheet. |
| **Drag-and-drop `.ff1` cache file load** | Power-user feature. Lets people run the model on local cached sessions without API round-trip. Zero competitors support this; FastF1 power users will notice immediately. |
| **Model version + calibration tag stamped on every prediction** | Scientific credibility. Journalists can cite "Model v1.0, calibration 2026-Q1" and reproduce later. None of the existing tools surface this. |
| **Right-click tire widget → copy metric to clipboard** | Tiny, but analysts will *love* this. Removes the "screenshot-and-transcribe" friction. |
| **Event log (Zone 7) surfacing model-detected events per lap** | "Lap 14: thermal saturation detected in RF", "Lap 18: grip falls below 85% threshold". Converts opaque physics into a readable narrative — teaches users what to look for. |
| **First-run tour highlighting one physics concept per zone** | The four minute learning curve for new users. Tooltip coach-marks over tire array → charts → transport → event log. Skippable. Progressive disclosure per NN/g principles. |
| **"Physics glossary" drawer (press `?` or click jargon)** | Terms like "brush model slip", "Hertzian contact", "cumulative sliding energy" need inline explanation. A `G` key or click-on-term opens a drawer with 2-sentence definitions linked to the Jupyter notebook. Removes the "I don't understand this" bounce. |

---

## Anti-Features (deliberately excluded from V1)

Each of these has a compelling argument in its favour. Building them in V1 destroys focus. Reasons logged so the temptation is resisted.

| Feature | Reason for exclusion |
|---|---|
| **User accounts / saved scenarios** | Already in PROJECT.md out-of-scope. URL hash sharing covers 95% of the collaboration use case. Accounts add auth, persistence, password reset, GDPR — weeks of work for marginal V1 value. |
| **What-if sliders / parameter overrides** | V2. Would require a second API path, live re-simulation, UI for parameter ranges, and risk users producing "fake physics" outputs. Ship the ground-truth predictor first. |
| **Pit window optimizer** | V2. Requires a track-position sim on top of the tire model. Out of scope per PROJECT.md. |
| **Compound comparison overlay** | V2. Depends on what-if. |
| **Driver comparison side-by-side** | V2. Doubles the layout complexity (two dashboards synced). Validate single-driver first. |
| **Real-time / live race mode** | Out of scope per PROJECT.md. FastF1 public feed latency makes it impractical and the physics model's calibration assumes post-race data quality. |
| **Embed / iframe support** | Tempting (bloggers would embed charts). Defer to V2. A single PNG export with a URL watermark covers the sharing case without auth/sandboxing complexity. |
| **PDF report export** | PNG+SVG+CSV covers 100% of downstream uses in V1. PDF adds a server-side renderer (puppeteer / weasyprint) that isn't justified yet. |
| **Annotation tools (draw on charts, text overlay)** | TracingInsights has these. Genuinely useful but a rabbit hole — selection, undo/redo, persistence, export-with-annotations. V2. |
| **Full mobile-optimized UX** | Already in PROJECT.md out-of-scope. View-only responsive is enough. |
| **Multi-language support** | F1 is global; resist anyway. English-only ships months faster. |
| **Theming / light mode toggle** | Dark theme is the motorsport convention and matches the spec. Adding light theme is a token-system refactor; do only if users ask loudly. |
| **Telemetry charts beyond the three in spec (throttle, brake, gear, DRS…)** | Tempting feature-creep — FastF1 exposes dozens of channels. V1 stays on the physics-model outputs (lap time, sliding power, tread temp). Raw telemetry overlays = V2. |
| **Onboarding video / product tour carousel** | First-run coach-marks (already a differentiator) are enough. Skip the slideshow — users close it anyway (NN/g finding). |
| **Chart annotation ("add note at lap 14")** | Requires persistence. URL hash can't carry arbitrary free text cleanly. Defer. |
| **Live collaboration (multiple cursors)** | Absurd for V1. Flagging only because someone will suggest it. |
| **AI chat / LLM explanation panel** | Absolutely not in V1. The event log (Zone 7) is the deterministic, auditable substitute. An LLM layer would undermine the "interpretable physics" thesis. |
| **Printable PDF "stint report"** | Users can print-to-PDF from the browser; if they want a curated report, they'll screenshot. V2. |

---

## UX Patterns to Follow

| Pattern | Why / Reference |
|---|---|
| **Skeleton screens for zone-by-zone hydration, not spinners** | NN/g: skeletons reduce perceived wait ~40% and prevent layout shift. Each of the 7 zones gets its own skeleton matching its shape. |
| **Phased progress text during simulation** | "1/7 Kinematics… 2/7 Vertical loads… 7/7 Degradation". Uses Smart Interface Design Patterns' guidance that visible progress with context makes waits feel shorter. Even if each phase is 300ms, users *see* the model thinking. |
| **Cancellation via Esc key during simulation** | If user changes selection mid-run, abort the request. Standard per Carbon's loading pattern. |
| **Client-side memoization keyed by (race, driver, stint, model_version)** | React `useMemo` / TanStack Query for exact-match cache hits. Server already caches telemetry; client caches simulation outputs. Makes scrubbing between previously-run stints feel instant. |
| **Shared X-axis time scale with `d3.scaleLinear().invert()` for hover-to-lap mapping** | Canonical D3 pattern (D3 by Observable, d3-brush docs). Hover event → invert pixel to lap index → broadcast lap index to all zones via a React context or Zustand store. |
| **Confidence interval as `d3.area` drawn *before* the median line** | Avoids the overlap/z-order bug. Standard per D3 graph gallery. 80% and 95% bands nested, lighter for wider. |
| **Viridis for sequential (temperature, energy), Okabe-Ito for categorical non-compound** | Okabe-Ito palette: `#E69F00 #56B4E9 #009E73 #F0E442 #0072B2 #D55E00 #CC79A7 #000000`. Viridis for temp gradient. Colorblind-safe by construction. |
| **Redundant encoding (shape + color) anywhere color carries meaning** | E.g., front tires have a dot marker, rear tires a square marker; in addition to the compound colors. Survives greyscale printing and CVD. |
| **Keyboard-first navigation with visible focus rings** | Skip-links, focus-visible outlines, `role="slider"` on the scrub bar, `aria-live` region for the event log. WCAG 2.2 AA floor. |
| **Progressive disclosure in the Physics Glossary** | 2-sentence definition at first level, "read more" expands to equation + paper citation. IxDF: matches revealed complexity to user engagement. |
| **First-run coach-marks, dismissible and revivable via `?` → "Take the tour"** | Per Pendo/UXPin guidance: tours must be skippable and replayable. |
| **"Last updated" timestamp + model/calibration version on every shared URL** | Data freshness pattern from BI tooling (elementary-data, Sifflet). Green dot if < 24h old, amber if older, tooltip explains. |
| **Debounced URL hash writes (250ms) during scrubbing** | Don't thrash history; write only when user stops scrubbing or selects. Prevents browser history spam. |
| **Empty-state hero with curated example stints** | Carbon "starter content" pattern. Three buttons: "Monaco 2023 – Verstappen – Stint 2", etc. Removes blank-slate paralysis. |
| **Right-click context menu for export on any chart/widget** | Consistent affordance across the app. Matches AnyChart / Highcharts user expectations. |
| **Error toasts that include the failing operation AND a retry button** | Not a plain "Something went wrong". Example: "FastF1 couldn't load 2024 Monaco – Hamilton. [Retry] [Try another race]". |
| **Unit suffixes always visible on axes and tooltips** | °C, MJ, %, m, s. Non-experts bounce on unlabelled numbers. |

---

## Feature Dependencies (V1 internal)

```
Race/driver/stint picker ─┬─► Telemetry fetch (FastF1)
                          │
                          └─► Simulation (POST /simulate)
                                    │
                                    ├─► Multi-chart panel (Zone 4)
                                    ├─► Tire array (Zone 3)
                                    ├─► Track map playback (Zone 2)
                                    ├─► Event log (Zone 7)
                                    └─► Transport bar state (Zone 6)
                                            │
                                            └─► URL hash state encoder
                                                      │
                                                      └─► Shareable deep link
```

- **Linked hover / brushing** depends on a single shared "current lap" store — build this first.
- **Confidence-interval rendering** depends on the API returning CI fields per lap — coordinate with backend schema early.
- **Keyboard shortcuts** depend on the transport bar state machine — don't bolt on after.
- **URL hash encoding** depends on all interactive state being in a single normalized store (Zustand/Redux). Plan for this at architecture time.

---

## Open Questions

1. **Confidence-interval visual idiom**: two nested bands (80% + 95%) vs. a single 95% band + error-bar markers vs. fan-chart. Pick one during design; all three have D3 precedent. *Recommendation: two nested bands for simplicity, toggleable.*
2. **Tour behaviour on repeat visits**: auto-show once and persist-dismissed in localStorage, or always on first-of-session? *Recommendation: localStorage-persisted, revivable via `?`.*
3. **Export scope**: does "Export CSV" mean the currently-visible chart or the full simulation output? *Recommendation: current chart by default, with a shift-click or menu option for "Export full simulation CSV".*
4. **Pit marker interaction**: clicking a pit marker — jump to that lap, or split-view stints? *Recommendation: V1 = jump to lap only; split-view is V2 comparison territory.*
5. **URL hash size budget**: full state could balloon (race + driver + stint + view + playback + tire selection + glossary open). Hash has no hard limit but >2KB feels gross. *Recommendation: encode only scenario-identifying fields + current lap; ephemeral UI state (glossary open) lives in memory.*
6. **Do we ship a light-theme toggle or not?** Motorsport convention = dark. Some publication workflows require light for print. *Recommendation: dark-only V1; add token-based theming only if users ask.*
7. **What's the guaranteed "first content" if telemetry fetch is slow?** Do we show the picker immediately, or gate the whole UI behind the initial `/races` load? *Recommendation: picker immediately with its own skeleton; lazy-load race list.*
8. **Does `POST /simulate` expose intermediate per-module outputs, or just the final per-lap prediction?** Affects whether the progress bar can show real phase progress vs. fake. *Recommendation: backend streams phase completion events (SSE or WebSocket) so the progress UI is honest; otherwise use a 7-step fake-progress animation timed to typical run duration.*
9. **CVD testing rigor**: do we just pick colorblind-safe palettes, or do we run Sim Daltonism / Coblis over screenshots as a gate? *Recommendation: automated palette choice + one manual pass in Sim Daltonism before ship.*
10. **Do we need an "About / Methodology" page for journalist credibility?** Not a feature per se, but a trust-building page. *Recommendation: yes, minimal — links to Jupyter notebook + paper citations + calibration provenance. One page, ~30 min of work, huge credibility payoff.*

---

## Sources

- [NN/g — Skeleton Screens 101](https://www.nngroup.com/articles/skeleton-screens/) (HIGH confidence)
- [Carbon Design System — Loading pattern](https://carbondesignsystem.com/patterns/loading-pattern/) (HIGH)
- [Carbon Design System — Empty states](https://carbondesignsystem.com/patterns/empty-states-pattern/) (HIGH)
- [PatternFly — Progress guidelines](https://www.patternfly.org/components/progress/design-guidelines/) (HIGH)
- [Smart Interface Design Patterns — Designing Better Loading and Progress UX](https://smart-interface-design-patterns.com/articles/designing-better-loading-progress-ux/) (MEDIUM)
- [Observable — Linked brushing](https://observablehq.com/blog/linked-brushing) (HIGH)
- [D3 by Observable — d3-brush](https://d3js.org/d3-brush) (HIGH)
- [D3 Graph Gallery — Line chart with confidence interval](https://d3-graph-gallery.com/graph/line_confidence_interval.html) (HIGH)
- [Reich Lab — d3-foresight](http://reichlab.io/d3-foresight/) (HIGH — direct precedent for CI-on-time-series)
- [Claus Wilke — Fundamentals of Data Visualization: Visualizing Uncertainty](https://clauswilke.com/dataviz/visualizing-uncertainty.html) (HIGH)
- [TracingInsights F1 Analytics](https://tracinginsights.com/) (MEDIUM — competitor reference)
- [F1 Tempo performance analysis tool](https://ai.techgeekers.com/tools/f1-tempo-free-formula-1-performance-analysis-tool) (MEDIUM — competitor reference)
- [Okabe-Ito + Viridis — Simplified Science Publishing color palettes](https://www.simplifiedsciencepublishing.com/resources/best-color-palettes-for-scientific-figures-and-data-visualizations) (HIGH)
- [arXiv — Accessible Color Sequences for Data Visualization](https://arxiv.org/pdf/2107.02270) (HIGH)
- [IxDF — Progressive Disclosure](https://ixdf.org/literature/topics/progressive-disclosure) (HIGH)
- [Pendo — Onboarding, Progressive Disclosure, Memory](https://www.pendo.io/pendo-blog/onboarding-progressive-disclosure/) (MEDIUM)
- [TanStack Router — URL as State discussion](https://github.com/TanStack/router/discussions/1249) (MEDIUM)
- [SayBackend — Share Zustand State via URL](https://www.saybackend.com/blog/2023-dec-zustand-url-state-sharing/) (MEDIUM)
- [W3C TAG — Usage Patterns For Client-Side URL parameters](https://www.w3.org/2001/tag/doc/hash-in-url) (HIGH)
- [Highcharts — Export module](https://www.highcharts.com/docs/export-module/export-module-overview) (HIGH — reference for expected export formats)
- [AnyChart — Exports common settings](https://docs.anychart.com/Common_Settings/Exports) (HIGH)
- [Elementary Data — Data Freshness Best Practices](https://www.elementary-data.com/post/data-freshness-best-practices-and-key-metrics-to-measure-success) (MEDIUM)
- [Sifflet — What Is Data Freshness in Data Observability?](https://www.siffletdata.com/blog/data-freshness) (MEDIUM)
- [SciChart — Realtime Telemetry Data Visualization in Formula One](https://www.scichart.com/blog/realtime-telemetry-datavisualisation-formulaone-motorsport/) (MEDIUM — motorsport viz reference)
- [OpenF1 API](https://openf1.org/) (HIGH — adjacent data source)
