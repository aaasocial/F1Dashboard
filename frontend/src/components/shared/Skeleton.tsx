interface PanelSkeletonProps {
  label?: string
}

export function PanelSkeleton({ label = 'LOADING...' }: PanelSkeletonProps) {
  return (
    <div style={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--panel-bg)',
      fontFamily: 'var(--mono)',
      fontSize: 10,
      letterSpacing: 2,
      color: 'var(--text-muted)',
      textAlign: 'center',
      padding: '0 16px',
    }}>
      {label}
    </div>
  )
}

interface SkeletonProps {
  width?: string | number
  height?: string | number
  style?: React.CSSProperties
}

export function Skeleton({ width = '100%', height = 16, style }: SkeletonProps) {
  return (
    <div style={{
      width,
      height,
      background: 'var(--rule-strong)',
      opacity: 0.5,
      ...style,
    }} />
  )
}
