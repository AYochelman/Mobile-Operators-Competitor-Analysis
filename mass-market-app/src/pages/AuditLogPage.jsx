import { useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api'

const ACTION_LABELS = {
  user_assigned:      'משתמש שויך',
  user_removed:       'משתמש הוסר',
  workspace_created:  'Workspace נוצר',
  workspace_updated:  'Workspace עודכן',
  branding_updated:   'מיתוג עודכן',
  scrape_triggered:   'סריקה הופעלה',
  refresh_triggered:  'רענון ידני',
  contact_sent:       'פנייה נשלחה',
  invite_created:     'הזמנה נוצרה',
  invite_accepted:    'הזמנה התקבלה',
  trial_expired:      'פיילוט פג',
  digest_sent:        'דייג׳סט נשלח',
}

const ACTION_COLORS = {
  user_assigned:     'bg-green-100 text-green-700',
  user_removed:      'bg-red-100 text-red-600',
  workspace_created: 'bg-blue-100 text-blue-700',
  workspace_updated: 'bg-amber-100 text-amber-700',
  branding_updated:  'bg-purple-100 text-purple-700',
  scrape_triggered:  'bg-gray-100 text-gray-600',
  refresh_triggered: 'bg-gray-100 text-gray-600',
  contact_sent:      'bg-teal-100 text-teal-700',
  invite_created:    'bg-indigo-100 text-indigo-700',
  invite_accepted:   'bg-emerald-100 text-emerald-700',
  trial_expired:     'bg-red-100 text-red-700',
  digest_sent:       'bg-sky-100 text-sky-700',
}

function ActionBadge({ action }) {
  const label = ACTION_LABELS[action] || action
  const color = ACTION_COLORS[action] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  )
}

export default function AuditLogPage() {
  const [entries, setEntries]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [wsFilter, setWsFilter] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const params = wsFilter ? `?workspace_id=${encodeURIComponent(wsFilter)}` : ''
      const data = await api.getAuditLog(params)
      setEntries(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [wsFilter])

  useEffect(() => { load() }, [load])

  const uniqueWorkspaces = [...new Set(entries.map(e => e.workspace_id).filter(Boolean))]

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="mb-5 flex items-center justify-between gap-4 flex-wrap">
        <p className="text-sm text-gray-500">פעולות מערכת — 200 אחרונות</p>
        <div className="flex items-center gap-2">
          {uniqueWorkspaces.length > 0 && (
            <select
              value={wsFilter}
              onChange={e => setWsFilter(e.target.value)}
              className="px-2 py-1.5 text-sm border border-moca-border rounded"
            >
              <option value="">כל ה-Workspaces</option>
              {uniqueWorkspaces.map(id => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          )}
          <button onClick={load}
            className="text-xs text-moca-bolt hover:underline px-2 py-1">
            רענן
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-moca-border overflow-hidden">
        {loading ? (
          <p className="text-sm text-gray-500 p-5">טוען…</p>
        ) : error ? (
          <p className="text-sm text-red-600 p-5">שגיאה: {error}</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-gray-500 p-5">אין רשומות.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b bg-gray-50/60">
                <th className="text-right py-2 px-4">זמן</th>
                <th className="text-right py-2 px-4">פעולה</th>
                <th className="text-right py-2 px-4">מבצע</th>
                <th className="text-right py-2 px-4">יעד</th>
                <th className="text-right py-2 px-4">פרטים</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id} className="border-b border-moca-border/20 hover:bg-gray-50/40">
                  <td className="py-2 px-4 text-xs text-gray-500 whitespace-nowrap">
                    {e.created_at
                      ? new Date(e.created_at).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' })
                      : '—'}
                  </td>
                  <td className="py-2 px-4">
                    <ActionBadge action={e.action} />
                  </td>
                  <td className="py-2 px-4 text-xs text-gray-700 max-w-[180px] truncate">
                    {e.actor_email || '—'}
                  </td>
                  <td className="py-2 px-4 text-xs text-gray-700 max-w-[180px] truncate">
                    {e.target_email || '—'}
                  </td>
                  <td className="py-2 px-4 text-xs text-gray-500 max-w-[220px] truncate">
                    {e.details || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
