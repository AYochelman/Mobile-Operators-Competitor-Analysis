import { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'

export default function PreferencesPage() {
  const { user } = useAuth()
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
      setMsg({ ok: true, text: 'נשמר' })
      setTimeout(() => setMsg(null), 2000)
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto p-6">
      <div className="mb-5">
        <h1 className="text-2xl font-bold">העדפות</h1>
        <p className="text-sm text-gray-500 mt-1">{user?.email}</p>
      </div>

      <div className="bg-white border border-moca-border/60 rounded-xl p-5">
        <h2 className="text-sm font-semibold mb-1">התראות דוא"ל</h2>
        <p className="text-xs text-gray-500 mb-4">קבלת דייג'סט שבועי של שינויי מחירים ותוכניות.</p>

        {loading ? (
          <p className="text-xs text-gray-400">טוען…</p>
        ) : (
          <label className="flex items-center justify-between gap-3 py-2 cursor-pointer">
            <div>
              <p className="text-sm font-medium text-gray-800">הסרה מרשימת התפוצה</p>
              <p className="text-xs text-gray-500 mt-0.5">לא תקבל עוד מיילים של דייג'סט. ניתן לחזור בכל עת.</p>
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
