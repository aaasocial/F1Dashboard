# Phase 4: Simulation API & Uncertainty Quantification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 04-simulation-api-uncertainty-quantification
**Areas discussed:** Simulate response shape, Overrides + CI bands, Session upload lifetime, Calibration summary scope

---

## Simulate Response Shape

| Option | Description | Selected |
|--------|-------------|----------|
| All three levels | Per-timestep + per-lap + per-stint in one JSON response. Meets roadmap spec literally. Payload ~3–5 MB, frontend gets everything in one round-trip. | ✓ |
| Per-lap + per-stint (default), per-timestep opt-in | Default response compact (~50 KB). `?detail=timestep` query param for full arrays. | |
| Per-lap + per-stint only | Track map animation deferred to separate endpoint or Phase 6. | |

**User's choice:** All three levels in one response.
**Notes:** Phase 5 needs all three levels simultaneously — track animation, lap charts, and stint summary.

---

## CI Band Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Triplet per value | `{"mean": 95.2, "lo_95": 88.1, "hi_95": 102.4}` per metric. Self-documenting, easy to destructure in TypeScript. | ✓ |
| Parallel arrays | Separate means[], lo_95[], hi_95[] arrays. More compact. Less ergonomic for frontend. | |

**User's choice:** Triplet per value.
**Notes:** Consistent structure across per-timestep, per-lap, and per-stint levels.

---

## Overrides + CI Bands

| Option | Description | Selected |
|--------|-------------|----------|
| Still run K=100 draws | Override applies to all K draws identically. CI bands from remaining posterior variance survive. Consistent response shape always. | ✓ |
| Switch to point estimate | Overrides replace posterior with deterministic run. Response drops CI bands, adds `override_mode: true` flag. | |

**User's choice:** Always run K=100 draws.
**Notes:** Override shifts all K draws equally; variance from non-overridden dims preserved. `overrides_applied` flag in metadata.

---

## Session Upload Lifetime

| Option | Description | Selected |
|--------|-------------|----------|
| Ephemeral: 1-hour TTL | Cleaned up after 1 hour. session_id returned in upload response, used as query param in /simulate. Simple, no accumulating storage. | ✓ |
| Persistent: survives restarts | Stored indefinitely (no DELETE in v1). Good for demos but sessions accumulate. | |

**User's choice:** 1-hour TTL ephemeral session.
**Notes:** session_id is a UUID. Background cleanup task (not cron). Sessions under `/data/sessions/{session_id}/`.

---

## Calibration Summary Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All four stages | Every fitted parameter with available uncertainty. Stage 4: full posterior. Stages 1–3: point estimate + residual uncertainty. Plus Stage 5 RMSE metrics. | ✓ |
| Stage 4 Bayesian params only | Only β_therm, T_act, k_wear with full posterior distribution. Stages 1–3 treated as implementation details. | |

**User's choice:** All four stages.
**Notes:** Full picture for model debugging. Includes calibration_id, compound, year_range metadata.

---

## Claude's Discretion

- Vectorization strategy for K=100 draws (numpy batch vs sequential threadpool vs JAX vmap)
- Exact JSON field names (snake_case)
- LRU cache max size
- ZIP extraction path traversal guard implementation
- Background TTL cleanup mechanism
- HTTP error status codes

## Deferred Ideas

- Streaming NDJSON response for per-timestep data (v2 if payload is a problem)
- DELETE /sessions/{session_id} explicit cleanup (v2)
- Async job queue for /simulate if K=100 blows 2s budget (ARQ + Redis upgrade path)
- Per-user session isolation (requires auth, out of scope v1)
- GET /calibration/{compound}/history (v2)
