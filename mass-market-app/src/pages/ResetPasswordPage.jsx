import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import Logo from '../components/Logo'

// Landing page for the Supabase password-recovery link. Supabase parses the
// recovery token from the URL on load and establishes a temporary session
// (PASSWORD_RECOVERY event); we then let the user set a new password.
export default function ResetPasswordPage() {
  const navigate = useNavigate()
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
      setTimeout(() => navigate('/home', { replace: true }), 1600)
    } catch (err) {
      setError(err.message || 'שגיאה בעדכון הסיסמה. ייתכן שהקישור פג תוקף.')
    } finally {
      setBusy(false)
    }
  }

  const inputCls = 'w-full border border-moca-border rounded-xl px-4 py-2.5 text-sm bg-moca-mist focus:ring-2 focus:ring-moca-bolt/30 focus:border-moca-bolt outline-none transition-all'

  return (
    <div className="min-h-screen flex items-center justify-center bg-moca-bg px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8 flex flex-col items-center">
          <Logo size="md" showSubtext={false} />
        </div>

        <div className="bg-white rounded-2xl shadow-card border border-moca-border p-7">
          {linkState === 'checking' && (
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="animate-spin h-7 w-7 border-4 border-moca-bolt border-t-transparent rounded-full" />
              <p className="text-sm text-moca-sub">מאמת קישור...</p>
            </div>
          )}

          {linkState === 'invalid' && (
            <div className="text-center space-y-4 py-2">
              <p className="text-sm text-moca-text">הקישור אינו תקין או שפג תוקפו.</p>
              <Link to="/login" className="inline-block text-sm text-moca-bolt underline">חזרה להתחברות</Link>
            </div>
          )}

          {linkState === 'ready' && (done ? (
            <div className="text-center space-y-3 py-2">
              <div className="text-3xl text-moca-down">✓</div>
              <p className="text-sm text-moca-text">הסיסמה עודכנה. מעבירים אותך לאפליקציה...</p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5">
              <h1 className="text-lg font-bold text-moca-dark text-center">בחירת סיסמה חדשה</h1>
              <div>
                <label className="block text-xs font-medium text-moca-text mb-1.5 text-right">סיסמה חדשה</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                  className={inputCls} dir="ltr" autoComplete="new-password" placeholder="לפחות 6 תווים" required />
              </div>
              <div>
                <label className="block text-xs font-medium text-moca-text mb-1.5 text-right">אימות סיסמה</label>
                <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                  className={inputCls} dir="ltr" autoComplete="new-password" required />
              </div>
              {error && <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2 text-right">{error}</p>}
              <button type="submit" disabled={busy}
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
