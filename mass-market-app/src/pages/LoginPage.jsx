import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Logo from '../components/Logo'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [mode, setMode] = useState('login')         // 'login' | 'forgot'
  const [resetSent, setResetSent] = useState(false)
  const [resetBusy, setResetBusy] = useState(false)
  const { signIn, sendPasswordReset, user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => { document.title = 'כניסה | MOCA' }, [])

  useEffect(() => {
    if (!loading && user) {
      const pendingInvite = sessionStorage.getItem('pending_invite')
      if (pendingInvite) {
        sessionStorage.removeItem('pending_invite')
        navigate(`/invite/${pendingInvite}`, { replace: true })
      } else {
        // "/" is the static marketing page (served by Netlify); the SPA dashboard
        // home lives at /home so a post-login refresh lands on the app, not the
        // landing.
        navigate('/home', { replace: true })
      }
    }
  }, [user, loading, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await signIn(email, password)
    } catch (err) {
      setError(err.message || 'שגיאה בהתחברות')
    } finally {
      setSubmitting(false)
    }
  }

  const handleForgot = async (e) => {
    e.preventDefault()
    setError('')
    setResetBusy(true)
    try {
      await sendPasswordReset(email)
    } catch {
      // Swallow — never reveal whether the email exists (enumeration safety).
    } finally {
      setResetSent(true)
      setResetBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-moca-bg" role="status">
        <div className="animate-spin h-8 w-8 border-4 border-moca-bolt border-t-transparent rounded-full" aria-hidden="true" />
        <span className="sr-only">טוען...</span>
      </div>
    )
  }

  if (user) return null

  return (
    <div className="min-h-screen flex items-center justify-center bg-moca-bg px-4">
      <div className="w-full max-w-sm">
        {/* Logo + Brand */}
        <div className="text-center mb-8 flex flex-col items-center">
          <Logo size="md" showSubtext={false} />
          <p className="text-moca-sub text-sm mt-3 tracking-wide">
            <span className="font-bold text-moca-espresso">M</span>obile{' '}
            <span className="font-bold text-moca-espresso">O</span>perators{' '}
            <span className="font-bold text-moca-espresso">C</span>ompetitor{' '}
            <span className="font-bold text-moca-espresso">A</span>nalysis
          </p>
        </div>

        {/* Login / forgot-password card */}
        {mode === 'login' ? (
          <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-card border border-moca-border p-7 space-y-5">
            <h1 className="text-base font-bold text-moca-dark text-center">כניסה למערכת</h1>
            <div>
              <label htmlFor="login-email" className="block text-xs font-medium text-moca-text mb-1.5">אימייל</label>
              <input
                id="login-email" autoComplete="email"
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                className="w-full border border-moca-border rounded-xl px-4 py-2.5 text-sm bg-moca-mist focus:border-moca-bolt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-moca-bolt transition-all"
                placeholder="name@example.com" required dir="ltr"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="block text-xs font-medium text-moca-text mb-1.5">סיסמה</label>
              <input
                id="login-password" autoComplete="current-password"
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                className="w-full border border-moca-border rounded-xl px-4 py-2.5 text-sm bg-moca-mist focus:border-moca-bolt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-moca-bolt transition-all"
                placeholder="••••••••" required dir="ltr"
              />
            </div>

            {error && (
              <p className="text-xs text-red-700 bg-red-50 rounded-lg px-3 py-2" role="alert">{error}</p>
            )}

            <button
              type="submit"
              disabled={submitting} aria-busy={submitting}
              className="w-full bg-moca-bolt text-white font-medium py-2.5 rounded-xl hover:bg-moca-dark disabled:opacity-50 transition-colors hover-press"
            >
              {submitting ? 'מתחבר...' : 'כניסה'}
            </button>

            <button
              type="button"
              onClick={() => { setMode('forgot'); setError(''); setResetSent(false) }}
              className="w-full text-center text-xs text-moca-sub hover:text-moca-bolt transition-colors"
            >
              שכחתי סיסמה
            </button>
          </form>
        ) : (
          <form onSubmit={handleForgot} className="bg-white rounded-2xl shadow-card border border-moca-border p-7 space-y-5">
            <div className="text-center">
              <h1 className="text-base font-bold text-moca-dark mb-1">איפוס סיסמה</h1>
              <p className="text-xs text-moca-sub">נשלח אליך קישור לאיפוס הסיסמה למייל.</p>
            </div>
            <div>
              <label htmlFor="forgot-email" className="block text-xs font-medium text-moca-text mb-1.5">אימייל</label>
              <input
                id="forgot-email" autoComplete="email"
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                className="w-full border border-moca-border rounded-xl px-4 py-2.5 text-sm bg-moca-mist focus:border-moca-bolt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-moca-bolt transition-all"
                placeholder="name@example.com" required dir="ltr"
              />
            </div>

            {resetSent && (
              <p className="text-xs text-moca-down bg-green-50 rounded-lg px-3 py-2 text-center" role="status">
                אם המייל קיים במערכת, נשלח אליו קישור לאיפוס.
              </p>
            )}

            <button
              type="submit"
              disabled={resetBusy || resetSent} aria-busy={resetBusy}
              className="w-full bg-moca-bolt text-white font-medium py-2.5 rounded-xl hover:bg-moca-dark disabled:opacity-50 transition-colors hover-press"
            >
              {resetBusy ? 'שולח...' : 'שלח קישור לאיפוס'}
            </button>

            <button
              type="button"
              onClick={() => { setMode('login'); setError(''); setResetSent(false) }}
              className="w-full text-center text-xs text-moca-sub hover:text-moca-bolt transition-colors"
            >
              חזרה להתחברות
            </button>
          </form>
        )}

        <p className="text-center text-[10px] text-moca-muted mt-6 mx-auto">
          Made by Alon Yochelman
        </p>
      </div>
    </div>
  )
}
