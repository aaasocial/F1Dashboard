import { useUIStore } from '../stores/useUIStore'
import type { LapData, Corner, CI } from './types'

/**
 * Format a tire's CI-mean metrics into the clipboard string defined by D-15:
 *   "FL | 94.2°C | Grip 1.31μ | Wear 3.2 MJ | Slip 2.1°"
 * - Corner is uppercase
 * - Tread temperature to 1 decimal
 * - Grip to 2 decimals
 * - Wear (e_tire) to 1 decimal
 * - Slip angle to 1 decimal
 */
export function formatTireMetrics(corner: Corner, lap: LapData): string {
  const t = lap[`t_tread_${corner}` as keyof LapData] as CI
  const g = lap[`grip_${corner}` as keyof LapData] as CI
  const e = lap[`e_tire_${corner}` as keyof LapData] as CI
  const s = lap[`slip_angle_${corner}` as keyof LapData] as CI
  return [
    corner.toUpperCase(),
    `${t.mean.toFixed(1)}°C`,
    `Grip ${g.mean.toFixed(2)}μ`,
    `Wear ${e.mean.toFixed(1)} MJ`,
    `Slip ${s.mean.toFixed(1)}°`,
  ].join(' | ')
}

/**
 * Write the formatted string to the system clipboard and surface a toast.
 */
export async function copyTireMetrics(corner: Corner, lap: LapData): Promise<void> {
  const text = formatTireMetrics(corner, lap)
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Permissions / non-secure context — still show toast so user knows it ran
    }
  }
  useUIStore.getState().showToast(`COPIED ${corner.toUpperCase()}`)
}
