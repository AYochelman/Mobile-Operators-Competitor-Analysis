import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'

const TABS = [
  { id: 'domestic', label: 'חבילות סלולר', icon: '📱' },
  { id: 'abroad', label: 'חו"ל', icon: '✈️' },
  { id: 'global', label: 'גלובלי', icon: '🌍' },
]

const CARRIERS = [
  { id: 'partner', label: 'פרטנר' },
  { id: 'pelephone', label: 'פלאפון' },
  { id: 'hotmobile', label: 'הוט מובייל' },
  { id: 'cellcom', label: 'סלקום' },
  { id: 'mobile019', label: '019' },
  { id: 'xphone', label: 'XPhone' },
  { id: 'wecom', label: 'We-Com' },
]

const GLOBAL_PROVIDERS = [
  { id: 'tuki', label: 'Tuki' },
  { id: 'globalesim', label: 'GlobaleSIM' },
  { id: 'airalo', label: 'Airalo' },
  { id: 'pelephone_global', label: 'GlobalSIM' },
  { id: 'esimo', label: 'eSIMo' },
  { id: 'simtlv', label: 'SimTLV' },
  { id: 'world8', label: '8 World' },
  { id: 'saily', label: 'Saily' },
  { id: 'holafly', label: 'Holafly' },
]

const CARRIER_COLORS = {
  partner: 'blue', pelephone: 'orange', hotmobile: 'red', cellcom: 'purple',
  mobile019: 'teal', xphone: 'pink', wecom: 'amber',
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'orange',
  esimo: 'purple', simtlv: 'teal', world8: 'pink', saily: 'blue', holafly: 'green',
}

const TAB_LABELS = { domestic: 'חבילות סלולר', abroad: 'חו"ל', global: 'גלובלי' }

function carrierLabel(id) {
  const all = [...CARRIERS, ...GLOBAL_PROVIDERS]
  return all.find(c => c.id === id)?.label || id || 'הכל'
}

function carriersForTab(tab) {
  if (tab === 'global') return GLOBAL_PROVIDERS
  return CARRIERS
}

export default function AlertsPage() {
  const { user } = useAuth()
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Form state
  const [formTab, setFormTab] = useState('domestic')
  const [formCarrier, setFormCarrier] = useState('')
  const [formPattern, setFormPattern] = useState('')
  const [formThreshold, setFormThreshold] = useState('')

  const email = user?.email || ''

  // Load alerts on mount
  useEffect(() => {
    if (!email) return
    setLoading(true)
    api.getAlerts(email)
      .then(setAlerts)
      .catch(err => console.error('Failed to load alerts:', err))
      .finally(() => setLoading(false))
  }, [email])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!formThreshold || isNaN(Number(formThreshold))) return
    setSubmitting(true)
    try {
      await api.createAlert({
        user_email: email,
        tab: formTab,
        carrier: formCarrier,
        plan_pattern: formPattern,
        threshold: Number(formThreshold),
      })
      // Reload alerts
      const updated = await api.getAlerts(email)
      setAlerts(updated)
      // Reset form
      setFormCarrier('')
      setFormPattern('')
      setFormThreshold('')
      setShowForm(false)
    } catch (err) {
      console.error('Failed to create alert:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await api.deleteAlert(id)
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch (err) {
      console.error('Failed to delete alert:', err)
    }
  }

  const availableCarriers = useMemo(() => carriersForTab(formTab), [formTab])

  return (
    <div className="max-w-3xl mx-auto px-4 py-6" dir="rtl">
      <div className="flex items-center justify-end mb-5">
        <Button
          variant={showForm ? 'secondary' : 'primary'}
          size="sm"
          onClick={() => setShowForm(v => !v)}
        >
          {showForm ? 'ביטול' : '+ הוספת התראה'}
        </Button>
      </div>

      {/* ── Create form ────────────────────────────────────────────── */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-white rounded-xl border border-gray-200 p-5 mb-5 space-y-4"
        >
          <p className="text-sm font-semibold text-gray-700 mb-1">התראה חדשה</p>

          {/* Tab select */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">סוג חבילה</label>
            <div className="flex gap-2">
              {TABS.map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setFormTab(t.id); setFormCarrier('') }}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    formTab === t.id
                      ? 'bg-blue-50 border-blue-300 text-blue-700'
                      : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {t.icon} {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Carrier select */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              ספק (אופציונלי)
            </label>
            <select
              value={formCarrier}
              onChange={e => setFormCarrier(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">הכל</option>
              {availableCarriers.map(c => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>

          {/* Plan pattern */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">חיפוש בשם חבילה (אופציונלי)</label>
            <input
              type="text"
              value={formPattern}
              onChange={e => setFormPattern(e.target.value)}
              placeholder='למשל: "50GB" או "אירופה"'
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Threshold */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">סף מחיר (&#8362;)</label>
            <input
              type="number"
              min="0"
              step="1"
              value={formThreshold}
              onChange={e => setFormThreshold(e.target.value)}
              placeholder="50"
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-[11px] text-gray-400 mt-1">תקבל התראה כשמחיר חבילה תואמת יורד מתחת לסכום זה</p>
          </div>

          <Button type="submit" variant="primary" size="md" disabled={submitting || !formThreshold}>
            {submitting ? 'שומר...' : 'שמור התראה'}
          </Button>
        </form>
      )}

      {/* ── Alerts list ────────────────────────────────────────────── */}
      {loading ? (
        <div className="text-center py-10 text-gray-400 text-sm">טוען...</div>
      ) : alerts.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <p className="text-3xl mb-3">🔔</p>
          <p className="text-gray-600 mb-2 font-medium">אין התראות פעילות</p>
          <p className="text-sm text-gray-400">הגדר התראת מחיר וקבל הודעה כשמחיר חבילה יורד מתחת לסכום שתבחר</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map(a => (
            <div
              key={a.id}
              className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between gap-3"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <Badge color={CARRIER_COLORS[a.carrier] || 'gray'}>
                    {carrierLabel(a.carrier)}
                  </Badge>
                  <Badge color="blue">{TAB_LABELS[a.tab] || a.tab}</Badge>
                  {a.plan_pattern && (
                    <span className="text-[11px] text-gray-400 truncate max-w-[140px]" title={a.plan_pattern}>
                      "{a.plan_pattern}"
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-700">
                  הודע כשמחיר &lt; <span className="font-semibold text-blue-600">&#8362;{a.threshold}</span>
                </p>
                {a.last_triggered && (
                  <p className="text-[11px] text-gray-400 mt-0.5">
                    הופעל לאחרונה: {new Date(a.last_triggered).toLocaleDateString('he-IL')}
                  </p>
                )}
              </div>
              <button
                onClick={() => handleDelete(a.id)}
                className="text-gray-400 hover:text-red-500 transition-colors p-1 rounded hover:bg-red-50"
                title="מחק התראה"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
