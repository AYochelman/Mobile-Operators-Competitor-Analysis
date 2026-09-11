import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import Logo from '../components/Logo'

// Landing page for the Supabase password-recovery link. Supabase parses the
// recovery token from the URL on load and establishes a temporary session
// (PASSWORD_RECOVERY event); we then let the user set a new password.
export default function ResetPasswordPage() {
  const [linkState, setLinkState] = useState('checking') // 'checking' | 'ready' | 'invalid'
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [error, setError]       = useState('')
  const [busy, setBusy]         = useState(false)
  const [done, setDone]         = useState(false)

  useEffect(() => {
    if (!supabase) { setLinkState('invalid'); return }
    let settled = false
    const markReady = () => { settled = true; setLinkState('ready') }
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' || session?.user) markReady()
    })
    supabase.auth.getSession().then(({ data: { session } }) => { if (session?.user) markReady() })
    // If no recovery session materialises, the link is bad or expired.
    const t = setTimeout(() => { if (!settled) setLinkState('invalid') }, 4000)
    return () => { subscription.unsubscribe(); clearTimeout(t) }
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 6)  { setError('הסיסמה חייבת להכיל לפחות 6 תווים'); return }
    if (password !== confirm) { setError('הסיסמאות אינן תואמות'); return }
    setBusy(true)
    try {
      const { error } = await supabase.auth.updateUser({ password })
      if (error) throw error
      setDone(true)
      // No timed auto-redirect (WCAG 2.2.1): the success view offers a link instead.
    } catch (err) {
      setError(err.message || 'שגיאה בעדכון הסיסמה. ייתכן שהקישור פג תוקף.')
    } finally {
      setBusy(false)
    }
  }

  const inputCls = 'w-full border border-moca-border rounded-xl px-4 py-2.5 text-sm bg-moca-mist focus:border-moca-bolt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-moca-bolt transition-all'

  useEffect(() => { document.title = 'איפוס סיסמה | MOCA' }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-moca-bg px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8 flex flex-col items-center">
          <Logo size="md" showSubtext={false} />
        </div>

        <div className="bg-white rounded-2xl shadow-card border border-moca-border p-7">
          {linkState === 'checking' && (
            <div className="flex flex-col items-center gap-3 py-4" role="status">
              <div className="animate-spin h-7 w-7 border-4 border-moca-bolt border-t-transparent rounded-full" aria-hidden="true" />
              <p className="text-sm text-moca-sub">מאמת קישור...</p>
            </div>
          )}

          {linkState === 'invalid' && (
            <div className="text-center space-y-4 py-2" role="alert">
              <h1 className="text-lg font-bold text-moca-dark">הקישור אינו תקין</h1>
              <p className="text-sm text-moca-text">הקישור אינו תקין או שפג תוקפו.</p>
              <Link to="/login" className="inline-block text-sm text-moca-bolt underline">חזרה להתחברות</Link>
            </div>
          )}

          {linkState === 'ready' && (done ? (
            <div className="text-center space-y-3 py-2" role="status">
              <div className="text-3xl text-moca-down" aria-hidden="true">✓</div>
              <h1 className="text-lg font-bold text-moca-dark">הסיסמה עודכנה</h1>
              <Link to="/home" className="inline-block text-sm text-moca-bolt underline">המשך לאפליקציה</Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5">
              <h1 className="text-lg font-bold text-moca-dark text-center">בחירת סיסמה חדשה</h1>
              <div>
                <label htmlFor="rp-password" className="block text-xs font-medium text-moca-text mb-1.5 text-right">סיסמה חדשה</label>
                <input id="rp-password" type="password" value={password} onChange={e => setPassword(e.target.value)}
                  className={inputCls} dir="ltr" autoComplete="new-password" aria-describedby="rp-hint" required />
                <p id="rp-hint" className="text-xs text-moca-sub mt-1 text-right">לפחות 6 תווים</p>
              </div>
              <div>
                <label htmlFor="rp-confirm" className="block text-xs font-medium text-moca-text mb-1.5 text-right">אימות סיסמה</label>
                <input id="rp-confirm" type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                  className={inputCls} dir="ltr" autoComplete="new-password" required />
              </div>
              {error && <p className="text-xs text-red-700 bg-red-50 rounded-lg px-3 py-2 text-right" role="alert">{error}</p>}
              <button type="submit" disabled={busy} aria-busy={busy}
                className="w-full bg-moca-bolt text-white font-medium py-2.5 rounded-xl hover:bg-moca-dark disabled:opacity-50 transition-colors hover-press">
                {busy ? 'מעדכן...' : 'עדכן סיסמה'}
              </button>
            </form>
          ))}
        </div>
      </div>
    </div>
  )
}
