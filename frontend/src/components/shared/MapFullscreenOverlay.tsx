import { useUIStore } from '../../stores/useUIStore'
import { MapPanel } from '../MapPanel/MapPanel'

export function MapFullscreenOverlay() {
  const open = useUIStore(s => s.mapFullscreen)
  const setOpen = useUIStore(s => s.setMapFullscreen)
  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Track map (fullscreen)"
      data-testid="map-fullscreen"
      onClick={() => setOpen(false)}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(5,7,11,0.85)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        data-testid="map-fullscreen-content"
        onClick={e => e.stopPropagation()}
        style={{
          width: '80vw',
          height: '80vh',
          background: 'var(--panel-bg)',
          border: '1px solid var(--rule-strong)',
          borderRadius: 0,
          position: 'relative',
          minHeight: 0,
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        <button
          onClick={() => setOpen(false)}
          aria-label="Close fullscreen map"
          style={{
            position: 'absolute', top: 8, right: 8, zIndex: 1,
            background: 'var(--panel)',
            border: '1px solid var(--rule-strong)',
            color: 'var(--text)',
            fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700,
            padding: '4px 9px', cursor: 'pointer', borderRadius: 0,
          }}
        >&#x2715;</button>
        <MapPanel />
      </div>
    </div>
  )
}
