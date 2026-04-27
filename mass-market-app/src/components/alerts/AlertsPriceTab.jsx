import { useState, useEffect, useMemo, useCallback } from 'react'
import { api } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { useHiddenCarrier } from '../../hooks/useHiddenCarrier'
import Button from '../ui/Button'
import Badge from '../ui/Badge'
import SearchableSelect from '../ui/SearchableSelect'

const TAB_ICONS = {
  domestic: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="2" width="14" height="20" rx="2" /><line x1="12" y1="18" x2="12.01" y2="18" />
    </svg>
  ),
  abroad: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" />
    </svg>
  ),
  global: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </svg>
  ),
}

const TABS = [
  { id: 'domestic', label: 'חבילות סלולר' },
  { id: 'abroad', label: 'חו"ל' },
  { id: 'global', label: 'גלובלי' },
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
  { id: 'esimio', label: 'eSIM.io' },
  { id: 'xphone_global', label: 'XPhone Global' },
  { id: 'sparks', label: 'Sparks' },
  { id: 'voye', label: 'VOYE' },
  { id: 'orbit', label: 'Orbit' },
  { id: 'travelsim', label: 'Travel Sim' },
  { id: 'gomoworld', label: 'GoMoWorld' },
  { id: 'tasim', label: 'Tasim' },
  { id: 'maya', label: 'Maya Mobile' },
  { id: 'bcengi', label: 'Bcengi' },
  { id: 'esim70', label: 'eSIM70' },
  { id: 'jetpack', label: 'Jetpack' },
]

const CARRIER_COLORS = {
  partner: 'blue', pelephone: 'orange', hotmobile: 'red', cellcom: 'purple',
  mobile019: 'teal', xphone: 'pink', wecom: 'amber',
  tuki: 'blue', globalesim: 'green', airalo: 'orange', pelephone_global: 'orange',
  esimo: 'purple', simtlv: 'teal', world8: 'pink', saily: 'blue', holafly: 'green',
  esimio: 'blue', xphone_global: 'teal', sparks: 'amber', voye: 'pink',
  orbit: 'indigo', travelsim: 'teal', gomoworld: 'cyan', tasim: 'purple',
  maya: 'teal', esim70: 'emerald', jetpack: 'sky',
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

export default function AlertsPriceTab() {
  const { user } = useAuth()
  const hiddenCarrier = useHiddenCarrier()
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Form state
  const [formTab, setFormTab] = useState('domestic')
  const [formCarrier, setFormCarrier] = useState('')
  const [formPlanName, setFormPlanName] = useState('')  // exact plan name selected
  const [formThreshold, setFormThreshold] = useState('')

  // Plans data for the dropdown
  const [plans, setPlans] = useState([])
  const [plansLoading, setPlansLoading] = useState(false)

  const email = user?.email || ''

  // Load alerts on mount
  useEffect(() => {
    if (!email) return
    setLoading(true)
    api.getAlerts()
      .then(setAlerts)
      .catch(err => console.error('Failed to load alerts:', err))
      .finally(() => setLoading(false))
  }, [email])

  // Fetch plans whenever tab or carrier changes (while form is open)
  useEffect(() => {
    if (!showForm) return
    setPlansLoading(true)
    setFormPlanName('')
    setFormThreshold('')

    const load = async () => {
      try {
        let data
        if (formTab === 'domestic') data = await api.getPlans()
        else if (formTab === 'abroad') data = await api.getAbroadPlans()
        else data = await api.getGlobalPlans()

        if (formCarrier) data = data.filter(p => p.carrier === formCarrier)
        setPlans(data || [])
      } catch (e) {
        console.error('Failed to load plans for alert form:', e)
        setPlans([])
      } finally {
        setPlansLoading(false)
      }
    }
    load()
  }, [formTab, formCarrier, showForm])

  // Build options for SearchableSelect — deduplicate by plan_name+carrier
  const planOptions = useMemo(() => {
    const seen = new Set()
    return plans
      .filter(p => {
        const key = `${p.carrier}__${p.plan_name}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
      .map(p => ({ value: p.plan_name, label: p.plan_name, price: p.price }))
  }, [plans])

  // When user selects a plan, auto-fill threshold with its current price
  const handlePlanSelect = useCallback((val) => {
    const planName = val === 'all' ? '' : val
    setFormPlanName(planName)
    if (!planName) { setFormThreshold(''); return }
    const opt = planOptions.find(o => o.value === planName)
    if (opt?.price != null) setFormThreshold(String(Math.round(opt.price)))
  }, [planOptions])

  const handleTabChange = (tabId) => {
    setFormTab(tabId)
    setFormCarrier('')
    setFormPlanName('')
    setFormThreshold('')
  }

  const handleCarrierChange = (e) => {
    setFormCarrier(e.target.value)
    setFormPlanName('')
    setFormThreshold('')
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!formThreshold || isNaN(Number(formThreshold))) return
    setSubmitting(true)
    try {
      await api.createAlert({
        user_email: email,
        tab: formTab,
        carrier: formCarrier,
        plan_pattern: formPlanName,
        threshold: Number(formThreshold),
      })
      const updated = await api.getAlerts()
      setAlerts(updated)
      setFormCarrier('')
      setFormPlanName('')
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

  const availableCarriers = useMemo(
    () => carriersForTab(formTab).filter(c => c.id !== hiddenCarrier),
    [formTab, hiddenCarrier]
  )

  // The selected plan's current price (for the hint label)
  const selectedPlanPrice = useMemo(() => {
    if (!formPlanName) return null
    return planOptions.find(o => o.value === formPlanName)?.price ?? null
  }, [formPlanName, planOptions])

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
                  onClick={() => handleTabChange(t.id)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    formTab === t.id
                      ? 'bg-blue-50 border-blue-300 text-blue-700'
                      : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span className="inline-flex items-center gap-1.5">{TAB_ICONS[t.id]}{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Carrier select */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">ספק (אופציונלי)</label>
            <SearchableSelect
              value={formCarrier || 'all'}
              onChange={v => handleCarrierChange({ target: { value: v === 'all' ? '' : v } })}
              options={availableCarriers.map(c => ({ value: c.id, label: c.label }))}
              placeholder="הכל"
              size="md"
            />
          </div>

          {/* Plan name dropdown */}
          <div>
            <label className="block text-xs text-gray-500 mb-1">חבילה (אופציונלי)</label>
            {plansLoading ? (
              <div className="flex items-center gap-2 py-2 text-xs text-gray-400">
                <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-6.22-8.56" /></svg>
                טוען חבילות...
              </div>
            ) : (
              <SearchableSelect
                value={formPlanName || 'all'}
                onChange={handlePlanSelect}
                options={planOptions}
                placeholder="כל החבילות"
                size="md"
              />
            )}
          </div>

          {/* Threshold */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-gray-500">סף מחיר (&#8362;)</label>
              {selectedPlanPrice != null && (
                <span className="text-[11px] text-gray-400">
                  מחיר נוכחי: <span className="font-medium text-gray-600">&#8362;{selectedPlanPrice}</span>
                </span>
              )}
            </div>
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
