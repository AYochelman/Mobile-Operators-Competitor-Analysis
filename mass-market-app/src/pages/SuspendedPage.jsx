import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'
import Logo from '../components/Logo'
import Button from '../components/ui/Button'

export default function SuspendedPage() {
  const { workspace, user, signOut } = useAuth()
  const name = workspace?.name || 'החשבון שלך'
  const isTrialExpired = workspace?.trial_expired === true

  const [formOpen, setFormOpen]   = useState(false)
  const [message, setMessage]     = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [status, setStatus]       = useState(null) // 'sent' | 'error' | null
  const [error, setError]         = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (!message.trim()) return
    setSubmitting(true); setError('')
    try {
      await api.sendContact(message.trim())
      setStatus('sent')
      setMessage('')
    } catch (err) {
      setStatus('error')
      setError(err.message || 'שליחה נכשלה')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-moca-bg px-4">
      <div className="w-full max-w-md text-center">
        <div className="flex justify-center mb-6">
          <Logo size="md" showSubtext={false} />
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-moca-border p-8 space-y-4">
          <div className="w-14 h-14 mx-auto rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#b45309"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>

          <h1 className="text-xl font-bold text-moca-text">
            {isTrialExpired ? 'תקופת הניסיון הסתיימה' : 'החשבון הושעה'}
          </h1>

          <p className="text-sm text-moca-sub leading-relaxed">
            {isTrialExpired ? (
              <>תקופת הפיילוט של <strong>{name}</strong> הגיעה לסיומה.
              צרו קשר כדי לחדש את הגישה או לעבור למנוי מלא.</>
            ) : (
              <>הגישה של <strong>{name}</strong> ל-MOCA הושהתה זמנית.
              אם לדעתך זו טעות או שברצונך לחדש את המנוי — פנה אלינו.</>
            )}
          </p>

          {status === 'sent' ? (
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl p-4 text-sm">
              ✓ הפנייה נשלחה. נחזור אליך בהקדם למייל {user?.email}.
            </div>
          ) : formOpen ? (
            <form onSubmit={submit} className="text-right space-y-3 pt-2">
              <label className="block text-xs text-moca-sub">
                הודעה ל-MOCA
                <textarea
                  value={message} onChange={e => setMessage(e.target.value)}
                  required maxLength={4000} rows={5}
                  placeholder="ספר לנו מה קרה או בקש לחדש את הגישה…"
                  className="mt-1 w-full px-3 py-2 border border-moca-border rounded-xl
                             text-sm focus:ring-2 focus:ring-moca-bolt/30
                             focus:border-moca-bolt outline-none"
                />
              </label>
              {error && <p className="text-xs text-red-600">{error}</p>}
              <div className="flex gap-2">
                <button type="submit" disabled={submitting || !message.trim()}
                  className="flex-1 bg-moca-bolt text-white font-medium py-2 rounded-xl
                             hover:bg-moca-dark disabled:opacity-50 transition-colors text-sm">
                  {submitting ? 'שולח…' : 'שלח פנייה'}
                </button>
                <Button type="button" onClick={() => setFormOpen(false)} variant="ghost">
                  ביטול
                </Button>
              </div>
            </form>
          ) : (
            <button onClick={() => { setFormOpen(true); setStatus(null) }}
              className="block w-full bg-moca-bolt text-white font-medium py-2.5 rounded-xl
                         hover:bg-moca-dark transition-colors">
              צור קשר עם MOCA
            </button>
          )}

          <Button onClick={signOut} variant="ghost" className="w-full">
            יציאה
          </Button>
        </div>

        <p className="text-[10px] text-moca-muted mt-6">
          MOCA — Mobile Operators Competitor Analysis
        </p>
      </div>
    </div>
  )
}
