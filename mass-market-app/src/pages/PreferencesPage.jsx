import { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'
import { useLang } from '../hooks/useLanguage'

export default function PreferencesPage() {
  const { user } = useAuth()
  const { tt } = useLang()
  const [optOut, setOptOut] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)
  const [msg, setMsg]         = useState(null)

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || ''}/api/my-context`, {
      credentials: 'include',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}`,
        'ngrok-skip-browser-warning': 'true',
      },
    })
      .then(r => r.json())
      .then(ctx => setOptOut(!!ctx.digest_opt_out))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const save = async (next) => {
    setSaving(true); setMsg(null)
    try {
      await api.updateMyPreferences({ digest_opt_out: next })
      setOptOut(next)
      setMsg({ ok: true, text: tt('נשמר', 'Saved') })
      setTimeout(() => setMsg(null), 2000)
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto p-6">
      {/* Page identity is owned by the Topbar (kicker + title); we keep
          only contextual meta here (the user's email) to avoid a duplicate H1. */}
      <p className="text-sm text-gray-500 mb-5">{user?.email}</p>

      <div className="bg-white border border-moca-border/60 rounded-xl p-5">
        <h2 className="text-sm font-semibold mb-1">{tt('התראות דוא"ל', 'Email notifications')}</h2>
        <p className="text-xs text-gray-500 mb-4">{tt('קבלת דייג\'סט שבועי של שינויי מחירים ותוכניות.', 'Receive a weekly digest of price and plan changes.')}</p>

        {loading ? (
          <p className="text-xs text-gray-400">{tt('טוען…', 'Loading…')}</p>
        ) : (
          <label className="flex items-center justify-between gap-3 py-2 cursor-pointer">
            <div>
              <p className="text-sm font-medium text-gray-800">{tt('הסרה מרשימת התפוצה', 'Unsubscribe from the mailing list')}</p>
              <p className="text-xs text-gray-500 mt-0.5">{tt('לא תקבל עוד מיילים של דייג\'סט. ניתן לחזור בכל עת.', 'You will no longer receive digest emails. You can resubscribe anytime.')}</p>
            </div>
            <input
              type="checkbox"
              checked={optOut}
              onChange={e => save(e.target.checked)}
              disabled={saving}
              className="w-5 h-5 accent-moca-bolt cursor-pointer"
            />
          </label>
        )}

        {msg && (
          <p className={`text-xs mt-3 ${msg.ok ? 'text-emerald-600' : 'text-red-600'}`}>{msg.text}</p>
        )}
      </div>
    </div>
  )
}
