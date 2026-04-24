import { useEffect, useRef } from 'react'
import { useSimulationStore } from '../stores/useSimulationStore'
import { useUIStore } from '../stores/useUIStore'

/**
 * useHashSync — Phase 5 + Phase 6 INT-04
 *
 * Hash format:
 *   #race={raceId}&driver={driverCode}&stint={stintIndex}&lap={lapNumber}
 *
 * On mount: parse hash, restore selection + lap.
 * On selection change: write race/driver/stint to hash.
 * On integer-lap change: write lap to hash.
 */
export function useHashSync(): void {
  const selectedRaceId = useSimulationStore(s => s.selectedRaceId)
  const selectedDriverCode = useSimulationStore(s => s.selectedDriverCode)
  const selectedStintIndex = useSimulationStore(s => s.selectedStintIndex)
  const setSelection = useSimulationStore(s => s.setSelection)
  const pos = useUIStore(s => s.pos)
  const seek = useUIStore(s => s.seek)

  const restored = useRef(false)
  const lastIntegerLap = useRef<number | null>(null)

  // Restore on mount
  useEffect(() => {
    if (restored.current) return
    restored.current = true

    const hash = window.location.hash.slice(1)
    if (!hash) return
    const params = new URLSearchParams(hash)
    const race = params.get('race')
    const driver = params.get('driver')
    const stintStr = params.get('stint')
    const lapStr = params.get('lap')

    if (race && driver && stintStr) {
      const stint = parseInt(stintStr, 10)
      if (!isNaN(stint)) setSelection(race, driver, stint)
    }
    if (lapStr) {
      const lap = parseInt(lapStr, 10)
      if (!isNaN(lap) && lap >= 1) {
        seek(lap)
        lastIntegerLap.current = lap
      }
    }
  }, [setSelection, seek])

  // Write selection (race/driver/stint) on change — preserve existing lap in hash
  useEffect(() => {
    if (selectedRaceId && selectedDriverCode && selectedStintIndex != null) {
      const cur = new URLSearchParams(window.location.hash.slice(1))
      cur.set('race', selectedRaceId)
      cur.set('driver', selectedDriverCode)
      cur.set('stint', String(selectedStintIndex))
      // lap stays in hash if already present (preserved across cascade changes)
      window.location.hash = cur.toString()
    }
  }, [selectedRaceId, selectedDriverCode, selectedStintIndex])

  // Write lap on integer-lap boundary crossing
  useEffect(() => {
    const intLap = Math.max(1, Math.floor(pos))
    if (intLap === lastIntegerLap.current) return
    lastIntegerLap.current = intLap
    // Only write if a stint is selected (otherwise lap is meaningless)
    if (!selectedRaceId || !selectedDriverCode || selectedStintIndex == null) return
    const cur = new URLSearchParams(window.location.hash.slice(1))
    cur.set('lap', String(intLap))
    window.location.hash = cur.toString()
  }, [pos, selectedRaceId, selectedDriverCode, selectedStintIndex])
}
