import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Logo from '../components/Logo'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { signIn, user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && user) {
      navigate('/', { replace: true })
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
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-moca-bg">
        <div className="animate-spin h-8 w-8 border-4 border-moca-bolt border-t-transparent rounded-full" />
      </div>
    )
  }

  if (user) return null

  return (
    <div className="min-h-screen flex items-center justify-center bg-moca-bg px-4">
      <div className="w-full max-w-sm">
        {/* Logo + Brand */}
        <div className="text-center mb-8">
          <Logo size="md" />
          <p className="text-moca-sub text-xs mt-2 tracking-wide">Competitive Intelligence Platform</p>
        </div>

        {/* Login card */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-moca-border p-7 space-y-5">
          <div>
            <label className="block text-xs font-medium text-moca-text mb-1.5">אימייל</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              className="w-full border border-moca-border rounded-xl px-4 py-2.5 text-sm bg-moca-mist focus:ring-2 focus:ring-moca-bolt/30 focus:border-moca-bolt outline-none transition-all"
              placeholder="name@example.com" required dir="ltr"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-moca-text mb-1.5">סיסמה</label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              className="w-full border border-moca-border rounded-xl px-4 py-2.5 text-sm bg-moca-mist focus:ring-2 focus:ring-moca-bolt/30 focus:border-moca-bolt outline-none transition-all"
              placeholder="••••••••" required dir="ltr"
            />
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-moca-bolt text-white font-medium py-2.5 rounded-xl hover:bg-moca-dark disabled:opacity-50 transition-colors hover-press"
          >
            {submitting ? '⏳ מתחבר...' : 'כניסה'}
          </button>
        </form>

        <p className="text-center text-[10px] text-moca-muted mt-6">
          Made by Alon Yochelman
        </p>
      </div>
    </div>
  )
}
