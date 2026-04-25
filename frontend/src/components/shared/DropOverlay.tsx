interface DropOverlayProps {
  active: boolean
  uploading: boolean
  progress: number
  error: string | null
}

export function DropOverlay({ active, uploading, progress, error }: DropOverlayProps) {
  if (!active && !uploading) return null

  return (
    <div
      role="dialog"
      aria-label={uploading ? 'Uploading FastF1 cache' : 'Drop FastF1 cache zip'}
      data-testid="drop-overlay"
      style={{
        position: 'fixed', inset: 0, zIndex: 120,
        background: 'rgba(5,7,11,0.85)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        pointerEvents: 'none',  // let drag/drop pass through to document.body
      }}
    >
      <div
        style={{
          minWidth: 480,
          padding: '40px 60px',
          border: '2px dashed var(--accent)',
          background: 'rgba(0,229,255,0.05)',
          fontFamily: 'var(--mono)',
          textAlign: 'center',
        }}
      >
        <div style={{
          fontSize: 14, color: 'var(--accent)',
          letterSpacing: 3, fontWeight: 700,
        }}>
          {uploading ? 'UPLOADING…' : 'DROP FASTF1 CACHE ZIP HERE'}
        </div>
        {uploading && (
          <div data-testid="upload-progress" style={{
            marginTop: 18, height: 6,
            background: 'var(--rule-strong)',
          }}>
            <div style={{
              height: '100%',
              width: `${Math.round(progress * 100)}%`,
              background: 'var(--accent)',
              transition: 'width 80ms linear',
            }} />
          </div>
        )}
        {error && !uploading && (
          <div style={{
            marginTop: 12, fontSize: 10, color: 'var(--hot)', letterSpacing: 1.4,
          }}>{error.toUpperCase()}</div>
        )}
      </div>
    </div>
  )
}
