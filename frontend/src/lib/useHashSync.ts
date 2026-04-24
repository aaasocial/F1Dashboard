import { useEffect } from 'react'
import { useSimulationStore } from '../stores/useSimulationStore'

/**
 * useHashSync — DASH-01
 *
 * Reads initial selection state from window.location.hash on mount and
 * writes any subsequent store selection changes back to the hash.
 *
 * Hash format: #race={raceId}&driver={driverCode}&stint={stintIndex}
 * Example:     #race=2024_bahrain&driver=LEC&stint=1
 *
 * No router dependency — implemented per CLAUDE.md guidance:
 * "Implement via a small custom hook syncing Zustand state ↔ window.location.hash
 * on change. Don't add a router for this."
 */
export function useHashSync(): void {
  const selectedRaceId = useSimulationStore(s => s.selectedRaceId)
  const selectedDriverCode = useSimulationStore(s => s.selectedDriverCode)
  const selectedStintIndex = useSimulationStore(s => s.selectedStintIndex)
  const setSelection = useSimulationStore(s => s.setSelection)

  // On mount: parse hash and pre-populate store so cascade pickers restore their state
  useEffect(() => {
    const hash = window.location.hash.slice(1)  // remove leading #
    if (!hash) return

    const params = new URLSearchParams(hash)
    const race = params.get('race')
    const driver = params.get('driver')
    const stintStr = params.get('stint')

    if (race && driver && stintStr) {
      const stint = parseInt(stintStr, 10)
      if (!isNaN(stint)) {
        setSelection(race, driver, stint)
      }
    }
  }, [setSelection])  // run once on mount

  // When store selection changes, write to hash (bookmarkable URL)
  useEffect(() => {
    if (selectedRaceId && selectedDriverCode && selectedStintIndex != null) {
      const params = new URLSearchParams({
        race: selectedRaceId,
        driver: selectedDriverCode,
        stint: String(selectedStintIndex),
      })
      window.location.hash = params.toString()
    }
  }, [selectedRaceId, selectedDriverCode, selectedStintIndex])
}
