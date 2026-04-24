import type { CSSProperties } from 'react'

interface SkeletonProps {
  width?: string | number
  height?: string | number
  style?: CSSProperties
}

export function Skeleton({ width = '100%', height = 20, style }: SkeletonProps) {
  return (
    <div style={{
      width,
      height,
      background: 'var(--rule-strong)',
      opacity: 0.6,
      animation: 'pulse-dot 1.4s ease infinite',
      ...style,
    }} />
  )
}

// Panel-level loading state — full panel skeleton
export function PanelSkeleton({ label }: { label: string }) {
  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--panel-bg)',
    }}>
      <div style={{
        height: 38,
        background: 'var(--panel-header)',
        borderBottom: '1px solid var(--rule)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 14px',
        gap: 10,
      }}>
        <div style={{ width: 2, height: 14, background: 'var(--rule-strong)' }} />
        <div style={{ width: 80, height: 10, background: 'var(--rule-strong)', opacity: 0.4 }} />
      </div>
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted)',
        fontFamily: 'var(--mono)',
        fontSize: 9,
        letterSpacing: 2,
      }}>
        {label}
      </div>
    </div>
  )
}
