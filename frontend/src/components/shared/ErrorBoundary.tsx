import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  label?: string
}
interface State {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', this.props.label, error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          background: 'var(--panel-bg)',
          fontFamily: 'var(--mono)',
          fontSize: 11,
          color: 'var(--hot)',
          letterSpacing: 1.4,
          padding: 16,
          flexDirection: 'column',
          gap: 8,
        }}>
          <span style={{ fontWeight: 700 }}>PANEL ERROR</span>
          <span style={{ color: 'var(--text-dim)', fontSize: 9, maxWidth: 280, textAlign: 'center' }}>
            {this.state.message}
          </span>
        </div>
      )
    }
    return this.props.children
  }
}
