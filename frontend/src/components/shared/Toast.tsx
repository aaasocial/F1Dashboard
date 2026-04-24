import { useEffect } from 'react'

interface ToastProps {
  message: string
  onDone: () => void
  durationMs?: number
}

export function Toast({ message, onDone, durationMs = 2000 }: ToastProps) {
  useEffect(() => {
    const t = window.setTimeout(onDone, durationMs)
    return () => window.clearTimeout(t)
  }, [onDone, durationMs])

  return (
    <div
      role="status"
      data-testid="toast"
      style={{
        position: 'fixed',
        top: 60,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 200,
        background: 'var(--panel)',
        border: '1px solid var(--accent)',
        color: 'var(--accent)',
        fontFamily: 'var(--mono)',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: 2,
        padding: '8px 20px',
        borderRadius: 0,
      }}
    >
      {message}
    </div>
  )
}
