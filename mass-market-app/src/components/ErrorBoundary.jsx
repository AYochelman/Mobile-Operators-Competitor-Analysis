import { Component } from 'react'

/**
 * Top-level React error boundary. Catches render-time errors in the route
 * tree and shows a recovery card instead of leaving the user with a blank
 * page. Without this, an uncaught error in a deep component (e.g.
 * DashboardPage) unmounts the whole tree.
 *
 * Browser console always gets the full stack via componentDidCatch.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] caught:', error, info?.componentStack)
    this.setState({ info })
  }

  reset = () => {
    this.setState({ error: null, info: null })
  }

  render() {
    if (!this.state.error) return this.props.children

    const message = this.state.error?.message || String(this.state.error)
    const stack = this.state.error?.stack || ''
    const componentStack = this.state.info?.componentStack || ''

    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--color-moca-bg)',
          padding: 20,
        }}
      >
        <div
          style={{
            maxWidth: 720,
            width: '100%',
            background: 'var(--color-moca-white, #fff)',
            border: '1px solid var(--color-moca-border)',
            borderRadius: 14,
            padding: 24,
            boxShadow: 'var(--sh-card)',
          }}
        >
          <div
            style={{
              fontSize: 10.5,
              color: 'var(--color-moca-up)',
              fontWeight: 800,
              letterSpacing: 0.6,
              textTransform: 'uppercase',
              marginBottom: 6,
            }}
          >
            ⚠ שגיאה בטעינת העמוד
          </div>
          <h1
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 22,
              fontWeight: 800,
              color: 'var(--color-moca-dark)',
              letterSpacing: -0.4,
              margin: '0 0 10px',
            }}
          >
            משהו השתבש
          </h1>
          <p style={{ fontSize: 13, color: 'var(--color-moca-sub)', lineHeight: 1.55, margin: '0 0 14px' }}>
            התרחשה שגיאה ברנדור של העמוד הזה. אפשר לנסות שוב או לחזור לדשבורד.
            הפרטים המלאים מודפסים ל-console (F12).
          </p>

          <div
            style={{
              background: 'var(--color-moca-mist)',
              border: '1px solid var(--color-moca-border)',
              borderRadius: 10,
              padding: 12,
              marginBottom: 16,
              fontFamily: 'ui-monospace, SFMono-Regular, monospace',
              fontSize: 12,
              color: 'var(--color-moca-text)',
              direction: 'ltr',
              maxHeight: 220,
              overflow: 'auto',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--color-moca-up)', marginBottom: 6 }}>
              {message}
            </div>
            {stack && (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 10.5, color: 'var(--color-moca-sub)' }}>
                {stack.split('\n').slice(0, 8).join('\n')}
              </pre>
            )}
            {componentStack && (
              <pre style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap', fontSize: 10.5, color: 'var(--color-moca-muted)' }}>
                {componentStack.split('\n').slice(0, 6).join('\n')}
              </pre>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={this.reset}
              style={{
                padding: '9px 18px',
                borderRadius: 10,
                background: 'var(--color-moca-bolt)',
                color: '#fff',
                border: 'none',
                fontSize: 13,
                fontWeight: 700,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              נסה שוב
            </button>
            <button
              type="button"
              onClick={() => { window.location.href = '/' }}
              style={{
                padding: '9px 18px',
                borderRadius: 10,
                background: 'var(--color-moca-white, #fff)',
                color: 'var(--color-moca-text)',
                border: '1px solid var(--color-moca-border)',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              לדשבורד
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: '9px 18px',
                borderRadius: 10,
                background: 'transparent',
                color: 'var(--color-moca-sub)',
                border: '1px solid var(--color-moca-border)',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              רענן את הדפדפן
            </button>
          </div>
        </div>
      </div>
    )
  }
}
