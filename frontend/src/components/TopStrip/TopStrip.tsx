import type React from 'react'
import { useRef, useCallback } from 'react'
import { useUIStore } from '../../stores/useUIStore'
import { useSimulationStore } from '../../stores/useSimulationStore'
import { useRaces, useDrivers, useStints } from '../../api/queries'
import { compoundColor } from '../../lib/scales'
import { runSimulationStream } from '../../lib/sse'
import { Scrubber } from './Scrubber'
import type { Race, Driver, Stint } from '../../lib/types'
import type { Speed } from '../../stores/useUIStore'

export function TopStrip() {
  const abortRef = useRef<AbortController | null>(null)

  const handleRunModel = useCallback(() => {
    const { selectedRaceId, selectedDriverCode, selectedStintIndex, loading } =
      useSimulationStore.getState()

    if (!selectedRaceId || !selectedDriverCode || selectedStintIndex == null) return
    if (loading) {
      // Cancel in-flight simulation if user clicks Run again
      abortRef.current?.abort()
      return
    }

    abortRef.current?.abort()  // abort any previous run
    const controller = new AbortController()
    abortRef.current = controller

    void runSimulationStream(
      selectedRaceId,
      selectedDriverCode,
      selectedStintIndex,
      controller.signal,
    )
  }, [])

  const pos = useUIStore(s => s.pos)
  const mode = useUIStore(s => s.mode)
  const playing = useUIStore(s => s.playing)
  const speed = useUIStore(s => s.speed)
  const setMode = useUIStore(s => s.setMode)
  const togglePlaying = useUIStore(s => s.togglePlaying)
  const setSpeed = useUIStore(s => s.setSpeed)
  const seek = useUIStore(s => s.seek)
  const setProvenanceOpen = useUIStore(s => s.setProvenanceOpen)

  const selectedRaceId = useSimulationStore(s => s.selectedRaceId)
  const selectedDriverCode = useSimulationStore(s => s.selectedDriverCode)
  const selectedStintIndex = useSimulationStore(s => s.selectedStintIndex)
  const data = useSimulationStore(s => s.data)
  const loading = useSimulationStore(s => s.loading)
  const moduleProgress = useSimulationStore(s => s.moduleProgress)
  const error = useSimulationStore(s => s.error)
  const lastRunParams = useSimulationStore(s => s.lastRunParams)
  const setError = useSimulationStore(s => s.setError)

  const { data: races, isLoading: racesLoading } = useRaces()
  const { data: drivers, isLoading: driversLoading } = useDrivers(selectedRaceId)
  const { data: stints, isLoading: stintsLoading } = useStints(selectedRaceId, selectedDriverCode)

  const maxLap = data?.laps.length ?? 22
  const lapNumber = Math.min(maxLap, Math.floor(pos))
  const lapFrac = pos - Math.floor(pos)

  // Derive session identity from simulation data or live cascade selection
  const currentDriver: Driver | null = data?.meta.driver
    ? { code: data.meta.driver.code, name: data.meta.driver.name, team: data.meta.driver.team, teamColor: data.meta.driver.teamColor }
    : (drivers?.find((d: Driver) => d.code === selectedDriverCode) ?? null)
  const currentStint = data?.meta.stint ?? null

  // SELECT handlers — cascade: race resets driver+stint, driver resets stint
  function onRaceChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const raceId = e.target.value || null
    // Reset to null so hash sync guard fires correctly (selectedStintIndex != null guard in useHashSync)
    useSimulationStore.setState({
      selectedRaceId: raceId ?? null,
      selectedDriverCode: null,
      selectedStintIndex: null,
    })
  }
  function onDriverChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const driverCode = e.target.value || null
    useSimulationStore.getState().setSelection(selectedRaceId ?? '', driverCode ?? '', 0)
  }
  function onStintChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const stintIdx = parseInt(e.target.value, 10)
    if (!isNaN(stintIdx)) {
      useSimulationStore.getState().setSelection(selectedRaceId ?? '', selectedDriverCode ?? '', stintIdx)
    }
  }

  // RETRY handler — re-fires last simulation with stored params
  const handleRetry = useCallback(() => {
    if (!lastRunParams) return
    setError(null)
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    void runSimulationStream(
      lastRunParams.raceId,
      lastRunParams.driverCode,
      lastRunParams.stintIndex,
      controller.signal,
    )
  }, [lastRunParams, setError])

  const dropdownStyle: React.CSSProperties = {
    background: 'var(--panel)',
    color: 'var(--text)',
    border: '1px solid var(--rule-strong)',
    fontFamily: 'var(--mono)',
    fontSize: 9.5,
    letterSpacing: 1.2,
    padding: '3px 6px',
    cursor: 'pointer',
    borderRadius: 0,
    minWidth: 120,
    outline: 'none',
  }

  const transportBtnStyle: React.CSSProperties = {
    background: 'transparent',
    border: '1px solid var(--rule-strong)',
    color: 'var(--text)',
    padding: '4px 8px',
    fontSize: 11,
    lineHeight: 1,
    fontWeight: 700,
    cursor: 'pointer',
    flexShrink: 0,
    fontFamily: 'var(--mono)',
    borderRadius: 0,
    minWidth: 26,
  }

  return (
    <>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'auto 1fr auto',
        alignItems: 'center',
        gap: 0,
        padding: '0 16px',
        background: 'var(--panel-header)',
        borderBottom: '1px solid var(--rule-strong)',
        fontFamily: 'var(--mono)',
        fontSize: 11,
        color: 'var(--text-dim)',
        letterSpacing: 1.2,
        height: 52,
        flexShrink: 0,
      }}>

        {/* LEFT BLOCK — session identity + cascade pickers + mode toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Team color tick */}
          <div style={{ width: 4, height: 22, background: currentDriver?.teamColor ?? '#DC0000', flexShrink: 0 }} />

          {/* Session identity */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: 'var(--text)', fontSize: 13, fontWeight: 700, letterSpacing: 2.2 }}>
                {currentDriver?.code ?? '---'}
              </span>
              <span style={{ color: 'var(--text-dim)', fontSize: 10.5, letterSpacing: 1.6 }}>
                · {currentDriver?.team?.toUpperCase() ?? '---'}
              </span>
            </div>
            {currentStint && (
              <div style={{ fontSize: 9.5, letterSpacing: 1.6, color: 'var(--text-dim)' }}>
                R{String(data?.meta.race.round ?? 0).padStart(2, '0')} · {data?.meta.race.name?.toUpperCase()} · STINT {currentStint.id}
                {' '}
                <span style={{ color: compoundColor(currentStint.compound), fontWeight: 700 }}>
                  {currentStint.compound}
                </span>
              </div>
            )}
          </div>

          {/* Vertical divider */}
          <div style={{ width: 1, height: 24, background: 'var(--rule-strong)' }} />

          {/* Cascade pickers — DASH-01 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <select
              style={dropdownStyle}
              value={selectedRaceId ?? ''}
              onChange={onRaceChange}
              disabled={racesLoading}
              aria-label="Select race"
            >
              <option value="">RACE…</option>
              {(races ?? []).map((r: Race) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>

            <select
              style={dropdownStyle}
              value={selectedDriverCode ?? ''}
              onChange={onDriverChange}
              disabled={!selectedRaceId || driversLoading}
              aria-label="Select driver"
            >
              <option value="">DRIVER…</option>
              {(drivers ?? []).map((d: Driver) => (
                <option key={d.code} value={d.code}>{d.code} — {d.team}</option>
              ))}
            </select>

            <select
              style={dropdownStyle}
              value={selectedStintIndex?.toString() ?? ''}
              onChange={onStintChange}
              disabled={!selectedDriverCode || stintsLoading}
              aria-label="Select stint"
            >
              <option value="">STINT…</option>
              {(stints ?? []).map((s: Stint, i: number) => (
                <option key={s.id} value={i.toString()}>S{s.id} — {s.compound} — {s.lapCount}L</option>
              ))}
            </select>

            {/* RUN MODEL */}
            <button
              onClick={handleRunModel}
              disabled={!selectedDriverCode || selectedStintIndex === null}
              style={{
                background: (!selectedDriverCode || selectedStintIndex === null) ? 'transparent' : 'var(--accent)',
                border: '1px solid var(--rule-strong)',
                color: (!selectedDriverCode || selectedStintIndex === null) ? 'var(--text-muted)' : '#000',
                fontFamily: 'var(--mono)',
                fontSize: 9.5,
                fontWeight: 700,
                letterSpacing: 1.5,
                padding: '3px 10px',
                cursor: (!selectedDriverCode || selectedStintIndex === null) ? 'not-allowed' : 'pointer',
                borderRadius: 0,
                flexShrink: 0,
              }}
            >
              RUN MODEL
            </button>
          </div>

          {/* Vertical divider */}
          <div style={{ width: 1, height: 24, background: 'var(--rule-strong)' }} />

          {/* Mode toggle — LIVE | REPLAY */}
          <div style={{ display: 'flex', border: '1px solid var(--rule-strong)', overflow: 'hidden' }}>
            {(['live', 'replay'] as const).map(m => (
              <button key={m} onClick={() => setMode(m)} style={{
                padding: '6px 12px',
                background: mode === m ? 'var(--accent)' : 'transparent',
                border: 'none',
                color: mode === m ? '#000' : 'var(--text-dim)',
                fontSize: 10, fontWeight: 700, letterSpacing: 2,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4,
                fontFamily: 'var(--mono)',
              }}>
                {m === 'live' && (
                  <span style={{
                    display: 'inline-block', width: 6, height: 6,
                    background: mode === 'live' ? '#000' : 'var(--hot)',
                    animation: mode !== 'live' ? 'blink-red 1.6s infinite' : 'none',
                  }} />
                )}
                {m.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* MIDDLE BLOCK — step/jump + play/pause + scrubber + speed toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 20px' }}>
          {/* Jump to first */}
          <button onClick={() => seek(1)} title="Jump to first lap (Home)" aria-label="Jump to first lap" style={transportBtnStyle}>⏮</button>
          {/* Step back */}
          <button onClick={() => seek(Math.max(1, Math.floor(pos) - 1))} title="Step back 1 lap (←)" aria-label="Step back 1 lap" style={transportBtnStyle}>◄</button>

          {/* Play/pause */}
          <button onClick={togglePlaying} aria-label={playing ? 'Pause' : 'Play'} style={{
            background: 'transparent', border: '1px solid var(--rule-strong)',
            color: 'var(--text)', padding: '4px 10px',
            fontSize: 10, letterSpacing: 1.5, fontWeight: 700, cursor: 'pointer', flexShrink: 0,
            fontFamily: 'var(--mono)', borderRadius: 0,
          }}>
            {playing ? '❚❚  PAUSE' : '►  PLAY'}
          </button>

          {/* Step forward */}
          <button onClick={() => seek(Math.min(maxLap, Math.floor(pos) + 1))} title="Step forward 1 lap (→)" aria-label="Step forward 1 lap" style={transportBtnStyle}>►</button>
          {/* Jump to last */}
          <button onClick={() => seek(maxLap)} title="Jump to last lap (End)" aria-label="Jump to last lap" style={transportBtnStyle}>⏭</button>

          {/* Module progress indicator (DASH-03) */}
          {loading && moduleProgress && (
            <span style={{ fontSize: 9, color: 'var(--accent-dim, var(--text-dim))', letterSpacing: 1.2, flexShrink: 0 }}>
              MODULE {moduleProgress.module}/7 — {moduleProgress.name.toUpperCase()}
            </span>
          )}

          <div style={{ flex: 1, minWidth: 80 }}>
            <Scrubber maxLap={maxLap} />
          </div>

          {/* Speed toggle — D-03: 0.5×/1×/2×/4× */}
          <div style={{ display: 'flex', gap: 0, border: '1px solid var(--rule-strong)', flexShrink: 0 }}>
            {([0.5, 1, 2, 4] as const).map((s: Speed) => (
              <button key={s} onClick={() => setSpeed(s)} aria-label={`Set playback speed ${s}×`} style={{
                padding: '4px 8px',
                background: speed === s ? 'var(--rule-strong)' : 'transparent',
                border: 'none',
                color: speed === s ? 'var(--text)' : 'var(--text-dim)',
                fontSize: 10, fontWeight: 600, minWidth: 28, cursor: 'pointer',
                fontFamily: 'var(--mono)', borderRadius: 0,
              }}>
                {s}×
              </button>
            ))}
          </div>
        </div>

        {/* RIGHT BLOCK — provenance button + lap counter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Provenance / about button — D-19 */}
          <button
            onClick={() => setProvenanceOpen(true)}
            aria-label="Open provenance / about"
            title="Provenance & disclaimer"
            style={{
              background: 'transparent',
              border: '1px solid var(--rule-strong)',
              color: 'var(--text-dim)',
              fontFamily: 'var(--mono)',
              fontSize: 11,
              fontWeight: 700,
              padding: '2px 7px',
              cursor: 'pointer',
              borderRadius: 0,
              lineHeight: 1.1,
            }}
          >ⓘ</button>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: 2 }}>LAP</div>
          <div style={{ color: 'var(--text)', fontSize: 22, fontWeight: 700, fontFamily: 'var(--mono)', letterSpacing: 1 }}>
            {String(lapNumber).padStart(2, '0')}
            <span style={{ color: 'var(--text-muted)', fontSize: 14, fontWeight: 400 }}> / {maxLap}</span>
          </div>
          <div style={{
            fontSize: 9, color: 'var(--text-dim)', letterSpacing: 1.5,
            padding: '3px 6px', border: '1px solid var(--rule)',
            fontFamily: 'var(--mono)',
          }}>
            {(lapFrac * 100).toFixed(0).padStart(2, '0')}% THRU
          </div>
        </div>
      </div>

      {/* Error banner — fixed below the 52px strip, zIndex 50 */}
      {error && (
        <div
          role="alert"
          data-testid="error-banner"
          style={{
            position: 'fixed', top: 52, left: 0, right: 0, zIndex: 50,
            background: 'rgba(255,51,68,0.12)',
            borderBottom: '1px solid var(--hot)',
            color: 'var(--hot)',
            fontFamily: 'var(--mono)',
            fontSize: 10,
            letterSpacing: 1.4,
            padding: '6px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <span style={{ flex: 1 }}>SIMULATION ERROR — {error.toUpperCase()}</span>
          <button
            onClick={handleRetry}
            disabled={!lastRunParams}
            style={{
              background: 'var(--hot)',
              color: '#000',
              border: '1px solid var(--hot)',
              fontFamily: 'var(--mono)',
              fontSize: 9.5,
              fontWeight: 700,
              letterSpacing: 1.5,
              padding: '3px 10px',
              cursor: lastRunParams ? 'pointer' : 'not-allowed',
              borderRadius: 0,
            }}
          >RETRY</button>
          <button
            onClick={() => setError(null)}
            aria-label="Dismiss error"
            style={{
              background: 'transparent',
              border: '1px solid var(--hot)',
              color: 'var(--hot)',
              fontFamily: 'var(--mono)',
              fontSize: 9.5,
              fontWeight: 700,
              padding: '3px 7px',
              cursor: 'pointer',
              borderRadius: 0,
            }}
          >✕</button>
        </div>
      )}
    </>
  )
}
