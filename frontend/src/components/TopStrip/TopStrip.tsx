import type React from 'react'
import { useUIStore } from '../../stores/useUIStore'
import { useSimulationStore } from '../../stores/useSimulationStore'
import { useRaces, useDrivers, useStints } from '../../api/queries'
import { compoundColor } from '../../lib/scales'
import { Scrubber } from './Scrubber'
import type { Race, Driver, Stint } from '../../lib/types'

export function TopStrip() {
  const pos = useUIStore(s => s.pos)
  const mode = useUIStore(s => s.mode)
  const playing = useUIStore(s => s.playing)
  const speed = useUIStore(s => s.speed)
  const setMode = useUIStore(s => s.setMode)
  const togglePlaying = useUIStore(s => s.togglePlaying)
  const setSpeed = useUIStore(s => s.setSpeed)

  const selectedRaceId = useSimulationStore(s => s.selectedRaceId)
  const selectedDriverCode = useSimulationStore(s => s.selectedDriverCode)
  const selectedStintIndex = useSimulationStore(s => s.selectedStintIndex)
  const data = useSimulationStore(s => s.data)
  const loading = useSimulationStore(s => s.loading)
  const moduleProgress = useSimulationStore(s => s.moduleProgress)

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
    useSimulationStore.getState().setSelection(raceId ?? '', '', 0)
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

  return (
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

          {/* RUN MODEL placeholder — wired in Plan 09 */}
          <button
            onClick={() => console.log('[TopStrip] RUN MODEL — wired in Plan 09')}
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

      {/* MIDDLE BLOCK — play/pause + scrubber + speed toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 20px' }}>
        <button onClick={togglePlaying} style={{
          background: 'transparent', border: '1px solid var(--rule-strong)',
          color: 'var(--text)', padding: '4px 10px',
          fontSize: 10, letterSpacing: 1.5, fontWeight: 700, cursor: 'pointer', flexShrink: 0,
          fontFamily: 'var(--mono)',
        }}>
          {playing ? '❚❚  PAUSE' : '►  PLAY'}
        </button>

        {/* Module progress indicator (DASH-03) */}
        {loading && moduleProgress && (
          <span style={{ fontSize: 9, color: 'var(--accent-dim)', letterSpacing: 1.2, flexShrink: 0 }}>
            MODULE {moduleProgress.module}/7 — {moduleProgress.name.toUpperCase()}
          </span>
        )}

        <div style={{ flex: 1, minWidth: 80 }}>
          <Scrubber maxLap={maxLap} />
        </div>

        {/* Speed toggle */}
        <div style={{ display: 'flex', gap: 0, border: '1px solid var(--rule-strong)', flexShrink: 0 }}>
          {([1, 2, 4, 8] as const).map(s => (
            <button key={s} onClick={() => setSpeed(s)} style={{
              padding: '4px 8px',
              background: speed === s ? 'var(--rule-strong)' : 'transparent',
              border: 'none',
              color: speed === s ? 'var(--text)' : 'var(--text-dim)',
              fontSize: 10, fontWeight: 600, minWidth: 28, cursor: 'pointer',
              fontFamily: 'var(--mono)',
            }}>
              {s}×
            </button>
          ))}
        </div>
      </div>

      {/* RIGHT BLOCK — lap counter */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
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
  )
}
