import type { ReactNode } from 'react'

interface PanelHeaderProps {
  title: string         // e.g. "CAR"
  subtitle?: string     // e.g. "SF-24 · TOP-DOWN · INTEGRATED TELEMETRY"
  right?: ReactNode
}

export function PanelHeader({ title, subtitle, right }: PanelHeaderProps) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '0 14px',
      background: 'var(--panel-header)',
      borderBottom: '1px solid var(--rule)',
      height: 38,
      fontFamily: 'var(--mono)',
      fontSize: 10,
      letterSpacing: 2,
      color: 'var(--text-dim)',
      flexShrink: 0,
    }}>
      {/* 2px left accent tick — present on every panel header */}
      <div style={{ width: 2, height: 14, background: 'var(--accent)', flexShrink: 0 }} />
      <span style={{ color: 'var(--text)', fontWeight: 700 }}>{title}</span>
      {subtitle && (
        <>
          <span style={{ color: 'var(--text-muted)' }}>·</span>
          <span>{subtitle}</span>
        </>
      )}
      {right && <span style={{ flex: 1 }} />}
      {right}
    </div>
  )
}
