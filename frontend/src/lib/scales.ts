import { interpolateViridis } from 'd3-scale-chromatic'

// Tire temperature → viridis color. 60°C = purple/blue end, 120°C = yellow end.
// Source: design reference data.jsx tempToViridis + README §Viridis temperature scale
export function tempToViridis(tempC: number): string {
  const t = Math.max(0, Math.min(1, (tempC - 60) / (120 - 60)))
  return interpolateViridis(t)
}

// Okabe-Ito colorblind-safe palette for FL/FR/RL/RR corners
// Source: design reference README §Physics Panel §Corner colors (Okabe–Ito)
export const CORNER_COLORS = {
  fl: '#E69F00', // orange
  fr: '#56B4E9', // sky blue
  rl: '#009E73', // teal-green
  rr: '#F0E442', // yellow
} as const

export const CORNER_LABELS = {
  fl: 'FL',
  fr: 'FR',
  rl: 'RL',
  rr: 'RR',
} as const

// FIA tire compound colors — exact values from design reference README §Tire compounds (FIA)
export const COMPOUND_COLORS = {
  SOFT:   '#FF3333',
  MEDIUM: '#FFD700',
  HARD:   '#FFFFFF',
  INTER:  '#22C55E',
  WET:    '#3B82F6',
} as const

export type CompoundName = keyof typeof COMPOUND_COLORS

export function compoundColor(compound: string): string {
  return COMPOUND_COLORS[compound.toUpperCase() as CompoundName] ?? '#999999'
}

// D3 scaleLinear domain helper with NaN guard
export function safeDomain(values: number[]): [number, number] {
  const finite = values.filter(isFinite)
  if (finite.length < 2) return [0, 1]
  return [Math.min(...finite), Math.max(...finite)]
}
