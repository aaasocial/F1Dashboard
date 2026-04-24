import type { LapData, CI } from './types'

/**
 * CSS custom property -> literal value map.
 * Copied verbatim from CLAUDE.md Design Lock; updates here MUST match CLAUDE.md.
 */
export const TOKEN_MAP: Record<string, string> = {
  'var(--bg)': '#05070b',
  'var(--panel)': '#0a0e15',
  'var(--panel-bg)': '#070a11',
  'var(--panel-header)': '#0c1119',
  'var(--panel-header-hi)': '#111827',
  'var(--rule)': '#1a2130',
  'var(--rule-strong)': '#2a3445',
  'var(--text)': '#e8eef7',
  'var(--text-dim)': '#6a7788',
  'var(--text-muted)': '#46525f',
  'var(--accent)': '#00E5FF',
  'var(--hot)': '#FF3344',
  'var(--warn)': '#FFB020',
  'var(--ok)': '#22E27A',
  'var(--purple)': '#A855F7',
  'var(--mono)': 'JetBrains Mono, monospace',
}

export type MetricKey = 't_tread' | 'grip' | 'e_tire' | 'slip_angle'

/** Substitute every var(--token) occurrence in an SVG string with its literal hex/value. */
export function substituteTokens(svgStr: string): string {
  let out = svgStr
  for (const [varRef, value] of Object.entries(TOKEN_MAP)) {
    out = out.split(varRef).join(value)
  }
  return out
}

/** Trigger a download for a Blob URL via a hidden <a>. */
export function triggerDownload(url: string, filename: string): void {
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/**
 * exportCsv — pure, fully unit-testable.
 * Builds: header row "lap,fl_mean,fl_lo95,fl_hi95,fr_mean,...,rr_hi95"
 * Then one row per lap with 13 columns: lap_number + 4 corners * 3 CI fields.
 */
export function buildCsv(laps: LapData[], metricKey: MetricKey): string {
  const corners = ['fl', 'fr', 'rl', 'rr'] as const
  const header = ['lap', ...corners.flatMap(c => [`${c}_mean`, `${c}_lo95`, `${c}_hi95`])].join(',')
  const rows = laps.map(lap => {
    const cells = corners.flatMap(c => {
      const ci = lap[`${metricKey}_${c}` as keyof LapData] as CI
      return [ci.mean.toFixed(4), ci.lo_95.toFixed(4), ci.hi_95.toFixed(4)]
    })
    return [String(lap.lap_number), ...cells].join(',')
  })
  return [header, ...rows].join('\n')
}

export function exportCsv(laps: LapData[], metricKey: MetricKey, filename = 'physics-data.csv'): void {
  const csv = buildCsv(laps, metricKey)
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  triggerDownload(URL.createObjectURL(blob), filename)
}

/**
 * exportSvg — clones SVG, substitutes CSS tokens, downloads.
 * Plan 04 implements full body. This is a working implementation.
 */
export function exportSvg(svgEl: SVGElement, filename = 'physics-chart.svg'): void {
  const clone = svgEl.cloneNode(true) as SVGElement
  const bbox = svgEl.getBoundingClientRect()
  clone.setAttribute('width', String(bbox.width))
  clone.setAttribute('height', String(bbox.height))
  if (!clone.getAttribute('xmlns')) {
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  }
  const serializer = new XMLSerializer()
  let svgStr = serializer.serializeToString(clone)
  svgStr = substituteTokens(svgStr)
  const blob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${svgStr}`], {
    type: 'image/svg+xml;charset=utf-8',
  })
  triggerDownload(URL.createObjectURL(blob), filename)
}

/**
 * exportPng — serialize SVG → <img> → <canvas> → toBlob.
 * Plan 04 wires this end-to-end into PhysicsPanel.
 */
export async function exportPng(svgEl: SVGElement, filename = 'physics-chart.png'): Promise<void> {
  const clone = svgEl.cloneNode(true) as SVGElement
  const bbox = svgEl.getBoundingClientRect()
  clone.setAttribute('width', String(bbox.width))
  clone.setAttribute('height', String(bbox.height))
  if (!clone.getAttribute('xmlns')) {
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  }
  const serializer = new XMLSerializer()
  let svgStr = serializer.serializeToString(clone)
  svgStr = substituteTokens(svgStr)
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgStr)}`

  await new Promise<void>((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const dpr = window.devicePixelRatio || 1
      const canvas = document.createElement('canvas')
      canvas.width = bbox.width * dpr
      canvas.height = bbox.height * dpr
      const ctx = canvas.getContext('2d')
      if (!ctx) return reject(new Error('canvas 2d context unavailable'))
      ctx.scale(dpr, dpr)
      ctx.drawImage(img, 0, 0)
      canvas.toBlob(blob => {
        if (!blob) return reject(new Error('canvas.toBlob returned null'))
        triggerDownload(URL.createObjectURL(blob), filename)
        resolve()
      }, 'image/png')
    }
    img.onerror = () => reject(new Error('SVG → image load failed'))
    img.src = url
  })
}
