import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import Button from '../components/ui/Button'
import HealthWidget from '../components/HealthWidget'
import AdminResetPasswordModal from '../components/AdminResetPasswordModal'
import { useAuth } from '../hooks/useAuth'
import { api } from '../lib/api'
import { useScrape } from '../hooks/useScrape'
import { refreshCoupons } from '../hooks/useCoupons'

const AFFILIATE_COMMISSION = { airalo: 0.10, holafly: 0.12, saily: 0.10, globalesim: 0.10 }
const AFFILIATE_AVG_ORDER  = { airalo: 18,   holafly: 20,   saily: 16,   globalesim: 15   }

export default function SettingsPage() {
  const { isAdmin, isSuperAdmin, user } = useAuth()
  const { scraping, triggerScrape } = useScrape()

  const [quota, setQuota] = useState(null)
  const prevScrapingRef = useRef(false)

  // Notification message language (he/en) — a global operator setting that
  // applies to every push channel (Telegram / WhatsApp / Web Push / Slack) and
  // the morning digest. Super-admin only.
  const [notifyLang, setNotifyLang]             = useState('he')
  const [notifyLangSaving, setNotifyLangSaving] = useState(false)

  useEffect(() => {
    api.getRefreshQuota().then(setQuota).catch(() => {})
  }, [])

  useEffect(() => {
    if (!isSuperAdmin) return
    api.getNotificationSettings()
      .then(r => setNotifyLang(r?.notify_lang === 'en' ? 'en' : 'he'))
      .catch(() => {})
  }, [isSuperAdmin])

  async function changeNotifyLang(lang) {
    if (lang === notifyLang || notifyLangSaving) return
    const prev = notifyLang
    setNotifyLang(lang)              // optimistic
    setNotifyLangSaving(true)
    try {
      const r = await api.setNotificationSettings(lang)
      setNotifyLang(r?.notify_lang === 'en' ? 'en' : 'he')
    } catch {
      setNotifyLang(prev)           // revert on failure
    } finally {
      setNotifyLangSaving(false)
    }
  }

  useEffect(() => {
    if (!scraping && prevScrapingRef.current) {
      api.getRefreshQuota().then(setQuota).catch(() => {})
    }
    prevScrapingRef.current = scraping
  }, [scraping])

  // Tab state — honour ?tab=<id> so other pages can deep-link (e.g. the user
  // activity dashboard's "ניהול משתמשים" button → /settings?tab=users).
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState(() => searchParams.get('tab') || 'scrape')

  // User management state
  const [users, setUsers]                   = useState([])
  const [usersLoading, setUsersLoading]     = useState(true)
  const [usersError, setUsersError]         = useState(null)
  const [showAddForm, setShowAddForm]       = useState(false)
  const [newEmail, setNewEmail]             = useState('')
  const [newPassword, setNewPassword]       = useState('')
  const [newRole, setNewRole]               = useState('viewer')
  const [addingUser, setAddingUser]         = useState(false)
  const [addError, setAddError]             = useState(null)
  const [deletingId, setDeletingId]         = useState(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [togglingId, setTogglingId]         = useState(null)
  const [resetPwUser, setResetPwUser]       = useState(null)

  // Affiliate state
  const [affiliateStats, setAffiliateStats]     = useState([])
  const [affiliateDays, setAffiliateDays]       = useState(30)
  const [affiliateLoading, setAffiliateLoading] = useState(false)
  const [affiliateAttr, setAffiliateAttr]       = useState(null)  // {by_source,by_campaign}

  // Coupons state (manually curated discount codes for global eSIM providers)
  const COUPON_BLANK = { carrier: '', code: '', discount_label: '', expires_at: '', source_url: '', notes: '', is_active: true, external_offer_url: '', partner_name: '' }
  const [coupons, setCoupons]               = useState([])
  const [couponsLoading, setCouponsLoading] = useState(false)
  const [couponsError, setCouponsError]     = useState(null)
  const [editingCoupon, setEditingCoupon]   = useState(null)  // null = closed, {} = new, {id,...} = edit
  const [couponForm, setCouponForm]         = useState(COUPON_BLANK)
  const [savingCoupon, setSavingCoupon]     = useState(false)
  const [couponSaveError, setCouponSaveError] = useState(null)

  // ── Stable callbacks (defined before useEffect) ──────────────────────────
  const loadUsers = useCallback(async () => {
    setUsersLoading(true)
    setUsersError(null)
    try {
      const data = await api.getUsers()
      setUsers(data)
    } catch (err) {
      setUsersError(err.message)
    }
    setUsersLoading(false)
  }, [])

  const loadAffiliateStats = useCallback(async () => {
    setAffiliateLoading(true)
    try {
      const [data, attr] = await Promise.all([
        api.getAffiliateStats(affiliateDays),
        api.getAffiliateAttribution(affiliateDays).catch(() => null),
      ])
      setAffiliateStats(data)
      setAffiliateAttr(attr)
    } catch {}
    setAffiliateLoading(false)
  }, [affiliateDays])

  const loadCoupons = useCallback(async () => {
    setCouponsLoading(true)
    setCouponsError(null)
    try {
      const data = await api.getAllCoupons()
      setCoupons(data || [])
    } catch (err) {
      setCouponsError(err.message)
    }
    setCouponsLoading(false)
  }, [])

  const openCouponForm = useCallback((row) => {
    setCouponSaveError(null)
    if (row && row.id) {
      setEditingCoupon(row)
      setCouponForm({
        carrier: row.carrier || '',
        code: row.code || '',
        discount_label: row.discount_label || '',
        expires_at: row.expires_at || '',
        source_url: row.source_url || '',
        notes: row.notes || '',
        is_active: !!row.is_active,
        external_offer_url: row.external_offer_url || '',
        partner_name: row.partner_name || '',
      })
    } else {
      setEditingCoupon({})
      setCouponForm(COUPON_BLANK)
    }
  }, [])

  const handleSaveCoupon = useCallback(async (e) => {
    e.preventDefault()
    setSavingCoupon(true)
    setCouponSaveError(null)
    try {
      const payload = {
        carrier: couponForm.carrier.trim().toLowerCase(),
        code: couponForm.code.trim(),
        discount_label: couponForm.discount_label.trim() || null,
        expires_at: couponForm.expires_at || null,
        source_url: couponForm.source_url.trim() || null,
        notes: couponForm.notes.trim() || null,
        is_active: !!couponForm.is_active,
        external_offer_url: couponForm.external_offer_url.trim() || null,
        partner_name: couponForm.partner_name.trim() || null,
      }
      if (editingCoupon?.id) {
        await api.updateCoupon(editingCoupon.id, payload)
      } else {
        await api.createCoupon(payload)
      }
      setEditingCoupon(null)
      setCouponForm(COUPON_BLANK)
      await loadCoupons()
      refreshCoupons()  // tell PlanCards to refetch
    } catch (err) {
      setCouponSaveError(err.message)
    }
    setSavingCoupon(false)
  }, [couponForm, editingCoupon, loadCoupons])

  const handleDeleteCoupon = useCallback(async (id) => {
    if (!window.confirm('למחוק את הקופון לצמיתות?')) return
    try {
      await api.deleteCoupon(id)
      await loadCoupons()
      refreshCoupons()
    } catch (err) {
      alert(err.message)
    }
  }, [loadCoupons])

  const handleToggleCouponActive = useCallback(async (row) => {
    try {
      await api.updateCoupon(row.id, { is_active: !row.is_active })
      await loadCoupons()
      refreshCoupons()
    } catch (err) {
      alert(err.message)
    }
  }, [loadCoupons])

  // ── Effects (must be before any conditional return) ──────────────────────
  // The "ניהול משתמשים" tab drives the global /api/users* endpoints, which are
  // now super_admin-only (cross-tenant writes locked server-side). Workspace
  // admins manage their own team via /workspace/users, so only load here for
  // super_admins — avoids a pointless fetch + a list they can't act on.
  useEffect(() => { if (isSuperAdmin) loadUsers() }, [loadUsers, isSuperAdmin])

  useEffect(() => {
    if (activeTab === 'affiliate') loadAffiliateStats()
  }, [activeTab, loadAffiliateStats])

  useEffect(() => {
    if (activeTab === 'coupons') loadCoupons()
  }, [activeTab, loadCoupons])

  // ── Derived data (must be before any conditional return) ─────────────────
  const affiliateSummary = useMemo(() => {
    const byProvider = {}
    affiliateStats.forEach(({ provider, clicks }) => {
      byProvider[provider] = (byProvider[provider] || 0) + clicks
    })
    return Object.entries(byProvider).map(([provider, clicks]) => ({
      provider,
      clicks,
      estimatedUsd: Math.round(
        clicks * 0.08 * (AFFILIATE_AVG_ORDER[provider] || 15) * (AFFILIATE_COMMISSION[provider] || 0.10) * 100
      ) / 100
    }))
  }, [affiliateStats])

  const affiliateChartData = useMemo(() => {
    const byDate = {}
    affiliateStats.forEach(({ date, clicks }) => {
      byDate[date] = (byDate[date] || 0) + clicks
    })
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, clicks]) => ({ date, clicks }))
  }, [affiliateStats])

  // ── Non-hook helpers (OK after hooks, before early return) ────────────────
  const handleAddUser = async (e) => {
    e.preventDefault()
    setAddingUser(true)
    setAddError(null)
    try {
      await api.createUser({ email: newEmail, password: newPassword, role: newRole })
      setNewEmail('')
      setNewPassword('')
      setNewRole('viewer')
      setShowAddForm(false)
      await loadUsers()
    } catch (err) {
      setAddError(err.message)
    }
    setAddingUser(false)
  }

  const handleDelete = async (id) => {
    setDeletingId(id)
    try {
      await api.deleteUser(id)
      setConfirmDeleteId(null)
      await loadUsers()
    } catch (err) {
      alert(err.message)
    }
    setDeletingId(null)
  }

  const handleToggleRole = async (u) => {
    setTogglingId(u.id)
    const newRole = u.role === 'admin' ? 'viewer' : 'admin'
    try {
      await api.updateUserRole(u.id, newRole)
      await loadUsers()
    } catch (err) {
      alert(err.message)
    }
    setTogglingId(null)
  }

  const isSelf = (u) => u.email === user?.email

  // ── Early return — AFTER all hooks ───────────────────────────────────────
  if (!isAdmin) return <div className="p-8 text-center text-gray-400">אין גישה</div>

  const TABS = [
    { id: 'scrape',    label: 'עדכון נתונים' },
    // Global user management (create/delete/re-role across all workspaces) is
    // super_admin-only. Workspace admins use "הצוות" (/workspace/users) for
    // their own, workspace-scoped team.
    ...(isSuperAdmin ? [{ id: 'users', label: 'ניהול משתמשים' }] : []),
    { id: 'affiliate', label: 'Affiliate' },
    { id: 'coupons',   label: 'קופונים' },
  ]

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">

      {/* Tab bar */}
      <div className="flex gap-2 border-b border-moca-border/40 pb-2">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors
              ${activeTab === t.id
                ? 'bg-moca-bolt text-white border-moca-bolt'
                : 'bg-white text-moca-bolt border-[#d4bfa8] hover:bg-moca-cream'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* === Scrape tab === */}
      {activeTab === 'scrape' && (
        <>
          {isSuperAdmin && <HealthWidget />}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="font-bold text-sm mb-3">סקרייפרים</h2>
            <p className="text-xs text-gray-400 mb-4">עדכון כל הנתונים אורך כ-12 דקות</p>
            <div className="flex items-center gap-3 flex-wrap">
              <Button onClick={triggerScrape} disabled={scraping || quota?.remaining === 0}>
                {scraping ? 'מעדכן...' : 'עדכן את כל הנתונים'}
              </Button>
              {quota && !quota.unlimited && (
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    {Array.from({ length: quota.limit }).map((_, i) => (
                      <span
                        key={i}
                        className={`inline-block w-2.5 h-2.5 rounded-full ${
                          i < quota.remaining ? 'bg-green-400' : 'bg-gray-200'
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-gray-500">
                    {quota.remaining} מתוך {quota.limit} רענונים נותרו החודש
                  </span>
                </div>
              )}
            </div>
            {quota && !quota.unlimited && quota.remaining === 0 && (
              <p className="text-xs text-red-500 mt-2">המכסה החודשית מוצתה. הרענון האוטומטי פועל כרגיל.</p>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="font-bold text-sm mb-3">תזמון</h2>
            <div className="text-sm text-gray-600 space-y-1">
              <p>סקרייפ אוטומטי: <strong>07:30</strong> ו-<strong>17:00</strong></p>
              <p>דוח Excel יומי: <strong>09:00</strong></p>
              <p>תקציר מנהלים: <strong>08:05</strong></p>
              <p>התראות: Telegram + Web Push בלבד על שינויים</p>
            </div>
          </div>

          {isSuperAdmin && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h2 className="font-bold text-sm mb-1">שפת ההתראות</h2>
              <p className="text-xs text-gray-400 mb-3">
                השפה של הודעות השינויים בכל הערוצים — Telegram · WhatsApp · Web Push · Slack ותקציר הבוקר.
                שמות החבילות הנסרקות נשארים בשפת המקור.
              </p>
              <div className="inline-flex rounded-full border border-[#d4bfa8] overflow-hidden">
                {[['he', 'עברית'], ['en', 'English']].map(([code, label]) => (
                  <button
                    key={code}
                    onClick={() => changeNotifyLang(code)}
                    disabled={notifyLangSaving}
                    className={`px-5 py-1.5 text-sm font-medium transition-colors disabled:opacity-60
                      ${notifyLang === code
                        ? 'bg-moca-bolt text-white'
                        : 'bg-white text-moca-bolt hover:bg-moca-cream'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {notifyLangSaving && <p className="text-xs text-gray-400 mt-2">שומר…</p>}
            </div>
          )}
        </>
      )}

      {/* === Users tab (super_admin only — global user management) === */}
      {activeTab === 'users' && isSuperAdmin && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold text-sm">ניהול משתמשים</h2>
            <Button size="sm" onClick={() => { setShowAddForm(!showAddForm); setAddError(null) }}>
              {showAddForm ? 'ביטול' : 'הוספת משתמש'}
            </Button>
          </div>

          {showAddForm && (
            <form onSubmit={handleAddUser} className="mb-4 p-3 bg-gray-50 rounded-lg space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">אימייל</label>
                <input
                  type="email"
                  required
                  value={newEmail}
                  onChange={e => setNewEmail(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="user@example.com"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">סיסמה</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="לפחות 6 תווים"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">תפקיד</label>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setNewRole('viewer')}
                    className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${newRole === 'viewer' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}>
                    צופה
                  </button>
                  <button type="button" onClick={() => setNewRole('admin')}
                    className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${newRole === 'admin' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}>
                    מנהל
                  </button>
                </div>
              </div>
              {addError && <p className="text-red-600 text-xs">{addError}</p>}
              <Button type="submit" size="sm" disabled={addingUser}>
                {addingUser ? 'יוצר...' : 'צור משתמש'}
              </Button>
            </form>
          )}

          {usersLoading ? (
            <p className="text-sm text-gray-400">טוען...</p>
          ) : usersError ? (
            <div className="text-sm text-red-600">
              <p>{usersError}</p>
              <button onClick={loadUsers} className="text-blue-600 underline text-xs mt-1">נסה שוב</button>
            </div>
          ) : users.length === 0 ? (
            <p className="text-sm text-gray-400">אין משתמשים</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-moca-border text-moca-sub text-xs">
                    <th className="text-right py-2 pr-1 font-medium w-20">תפקיד</th>
                    <th className="text-center py-2 font-medium">אימייל</th>
                    <th className="text-center py-2 font-medium whitespace-nowrap">התחבר לאחרונה</th>
                    <th className="py-2 pl-1"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} className="border-b border-moca-border/50 last:border-0 hover:bg-moca-mist transition-colors">
                      <td className="py-2.5 pr-1 text-right">
                        <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium ${u.role === 'admin' ? 'bg-moca-cream text-moca-bolt' : 'bg-gray-100 text-gray-500'}`}>
                          {u.role === 'admin' ? 'מנהל' : 'צופה'}
                        </span>
                      </td>
                      <td className="py-2.5 text-moca-text text-center" dir="ltr">
                        {u.email}
                        {isSelf(u) && <span className="text-xs text-moca-sub mr-1">(אתה)</span>}
                      </td>
                      <td className="py-2.5 text-center text-xs text-moca-sub whitespace-nowrap" dir="ltr">
                        {u.last_sign_in_at
                          ? new Date(u.last_sign_in_at).toLocaleString('he-IL', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
                          : '—'}
                      </td>
                      <td className="py-2.5 pl-1">
                        <div className="flex items-center gap-1.5 justify-end">
                          {!isSelf(u) && (
                            <>
                              <button onClick={() => handleToggleRole(u)} disabled={togglingId === u.id}
                                className="text-xs px-2.5 py-1.5 rounded-lg border border-moca-bolt/30 text-moca-bolt hover:bg-moca-cream disabled:opacity-40 transition-colors whitespace-nowrap"
                                title={u.role === 'admin' ? 'הורד לצופה' : 'הפוך למנהל'}>
                                {togglingId === u.id ? '...' : u.role === 'admin' ? 'הורד לצופה' : 'הפוך למנהל'}
                              </button>
                              <button onClick={() => setResetPwUser(u)}
                                className="text-xs px-2.5 py-1.5 rounded-lg border border-moca-bolt/30 text-moca-bolt hover:bg-moca-cream transition-colors whitespace-nowrap"
                                title="אפס סיסמה">
                                אפס סיסמה
                              </button>
                              {confirmDeleteId === u.id ? (
                                <>
                                  <button onClick={() => handleDelete(u.id)} disabled={deletingId === u.id}
                                    className="text-xs px-2.5 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 transition-colors whitespace-nowrap">
                                    {deletingId === u.id ? '...' : 'אשר מחיקה'}
                                  </button>
                                  <button onClick={() => setConfirmDeleteId(null)}
                                    className="text-xs px-2.5 py-1.5 rounded-lg border border-moca-bolt/30 text-moca-bolt hover:bg-moca-cream transition-colors">
                                    בטל
                                  </button>
                                </>
                              ) : (
                                <button onClick={() => setConfirmDeleteId(u.id)}
                                  className="text-xs px-2.5 py-1.5 rounded-lg border border-red-300 text-red-600 hover:bg-red-50 transition-colors whitespace-nowrap">
                                  מחק
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <AdminResetPasswordModal user={resetPwUser} onClose={() => setResetPwUser(null)} />
        </div>
      )}

      {/* === Affiliate tab === */}
      {activeTab === 'affiliate' && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="font-bold text-sm mb-4">Affiliate Analytics</h2>

          <div className="flex gap-2 mb-4 items-center">
            <span className="text-sm text-[#8b6b52] font-medium">תקופה:</span>
            {[7, 30, 90].map(d => (
              <button key={d} onClick={() => setAffiliateDays(d)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
                  ${affiliateDays === d ? 'bg-moca-bolt text-white border-moca-bolt' : 'bg-white text-moca-bolt border-[#d4bfa8] hover:bg-moca-cream'}`}>
                {d} ימים
              </button>
            ))}
          </div>

          {affiliateLoading && <p className="text-sm text-gray-400">טוען...</p>}

          {!affiliateLoading && (
            <>
              <table className="w-full text-sm mb-6 border-separate border-spacing-y-1">
                <thead>
                  <tr className="text-[#8b6b52] text-right text-xs">
                    <th className="font-medium pb-2">ספק</th>
                    <th className="font-medium pb-2">קליקים</th>
                    <th className="font-medium pb-2">הכנסה משוערת</th>
                  </tr>
                </thead>
                <tbody>
                  {affiliateSummary.length === 0 && (
                    <tr><td colSpan={3} className="text-center text-gray-400 py-4">אין נתונים עדיין</td></tr>
                  )}
                  {affiliateSummary.map(row => (
                    <tr key={row.provider} className="bg-gray-50 rounded-lg">
                      <td className="px-3 py-2 rounded-r-lg font-medium">{row.provider}</td>
                      <td className="px-3 py-2">{row.clicks}</td>
                      <td className="px-3 py-2 rounded-l-lg text-green-700 font-medium">${row.estimatedUsd}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {affiliateChartData.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-moca-bolt mb-3">קליקים לפי יום</p>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={affiliateChartData}>
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                      <Tooltip />
                      <Line type="monotone" dataKey="clicks" stroke="#5c3317" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {affiliateAttr && (
                <div className="mt-6 grid sm:grid-cols-2 gap-5">
                  <div>
                    <p className="text-sm font-medium text-moca-bolt mb-2">לפי ערוץ (src)</p>
                    {(affiliateAttr.by_source || []).length === 0 ? (
                      <p className="text-xs text-gray-400 py-2">אין נתונים עדיין</p>
                    ) : (
                      <table className="w-full text-sm border-separate border-spacing-y-1">
                        <tbody>
                          {affiliateAttr.by_source.map(r => (
                            <tr key={r.src} className="bg-gray-50">
                              <td className="px-3 py-2 rounded-r-lg font-medium">{r.src === 'esim' ? 'eSIM B2C' : r.src}</td>
                              <td className="px-3 py-2 rounded-l-lg text-left">{r.clicks}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-moca-bolt mb-2">לפי קמפיין (פוסט/סרטון)</p>
                    {(affiliateAttr.by_campaign || []).length === 0 ? (
                      <p className="text-xs text-gray-400 py-2">אין עדיין קליקים מתויגים. הוסיפו <code>?campaign=…</code> לקישורים בפוסטים.</p>
                    ) : (
                      <table className="w-full text-sm border-separate border-spacing-y-1">
                        <tbody>
                          {affiliateAttr.by_campaign.map(r => (
                            <tr key={r.campaign + r.src} className="bg-gray-50">
                              <td className="px-3 py-2 rounded-r-lg font-medium">{r.campaign}</td>
                              <td className="px-3 py-2 text-gray-400 text-xs">{r.src}</td>
                              <td className="px-3 py-2 rounded-l-lg text-left">{r.clicks}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* === Coupons tab === */}
      {activeTab === 'coupons' && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-bold text-sm">קופונים — קודי הנחה לספקים גלובליים</h2>
            <Button size="sm" onClick={() => openCouponForm(null)} disabled={!!editingCoupon}>
              הוספת קופון
            </Button>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            הקופון מוצג כתג קטן על כרטיס התוכנית בכל הספקים תחת מזהה ה-carrier. השדה
            <span className="font-mono mx-1">carrier</span>
            הוא ה-id באנגלית (למשל <span className="font-mono">saily</span>, <span className="font-mono">holafly</span>, <span className="font-mono">airalo</span>).
          </p>

          {editingCoupon && (
            <form onSubmit={handleSaveCoupon} className="mb-4 p-3 bg-gray-50 rounded-lg space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">carrier (id באנגלית)</label>
                  <input type="text" required dir="ltr"
                    value={couponForm.carrier}
                    onChange={e => setCouponForm({ ...couponForm, carrier: e.target.value })}
                    placeholder="saily"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">code</label>
                  <input type="text" required dir="ltr"
                    value={couponForm.code}
                    onChange={e => setCouponForm({ ...couponForm, code: e.target.value })}
                    placeholder="GIZMODO"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">תיאור הנחה (יוצג ליד הקוד)</label>
                  <input type="text"
                    value={couponForm.discount_label}
                    onChange={e => setCouponForm({ ...couponForm, discount_label: e.target.value })}
                    placeholder="15% הנחה"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">פג תוקף (אופציונלי)</label>
                  <input type="date" dir="ltr"
                    value={couponForm.expires_at}
                    onChange={e => setCouponForm({ ...couponForm, expires_at: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">מקור (URL לאימות)</label>
                  <input type="url" dir="ltr"
                    value={couponForm.source_url}
                    onChange={e => setCouponForm({ ...couponForm, source_url: e.target.value })}
                    placeholder="https://..."
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">הערות (פנימי)</label>
                  <textarea rows={2}
                    value={couponForm.notes}
                    onChange={e => setCouponForm({ ...couponForm, notes: e.target.value })}
                    placeholder="מותנה בקנייה ראשונה / מקור: cybernews"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div className="sm:col-span-2 pt-2 border-t border-gray-200">
                  <p className="text-xs text-gray-500 mb-2">
                    <strong>הצעה חיצונית</strong> — כשהשדות למטה מלאים, התג בכרטיס מתחלף לקישור-יציאה במקום קוד להעתקה
                    (לדוגמה: <span className="font-mono">https://www.gooday.co.il/.../Airalo</span> שמייצר קוד אישי למשתמש).
                  </p>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">שם הפרטנר (יוצג ליד ההטבה)</label>
                  <input type="text"
                    value={couponForm.partner_name}
                    onChange={e => setCouponForm({ ...couponForm, partner_name: e.target.value })}
                    placeholder="גודיי"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">כתובת ההצעה החיצונית</label>
                  <input type="url" dir="ltr"
                    value={couponForm.external_offer_url}
                    onChange={e => setCouponForm({ ...couponForm, external_offer_url: e.target.value })}
                    placeholder="https://www.gooday.co.il/הטבות/Airalo"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox"
                  checked={couponForm.is_active}
                  onChange={e => setCouponForm({ ...couponForm, is_active: e.target.checked })} />
                <span>פעיל (יוצג למשתמשים)</span>
              </label>
              {couponSaveError && <p className="text-red-600 text-xs">{couponSaveError}</p>}
              <div className="flex gap-2">
                <Button type="submit" size="sm" disabled={savingCoupon}>
                  {savingCoupon ? 'שומר...' : (editingCoupon?.id ? 'עדכן' : 'צור')}
                </Button>
                <Button type="button" size="sm" variant="ghost"
                  onClick={() => { setEditingCoupon(null); setCouponSaveError(null) }}>
                  ביטול
                </Button>
              </div>
            </form>
          )}

          {couponsLoading ? (
            <p className="text-sm text-gray-400">טוען...</p>
          ) : couponsError ? (
            <div className="text-sm text-red-600">
              <p>{couponsError}</p>
              <button onClick={loadCoupons} className="text-blue-600 underline text-xs mt-1">נסה שוב</button>
            </div>
          ) : coupons.length === 0 ? (
            <p className="text-sm text-gray-400">אין קופונים. לחץ "הוספת קופון" כדי להתחיל.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-moca-border text-moca-sub text-xs">
                    <th className="text-right py-2 pr-1 font-medium">ספק</th>
                    <th className="text-right py-2 font-medium">קוד</th>
                    <th className="text-right py-2 font-medium">תיאור</th>
                    <th className="text-right py-2 font-medium">תוקף</th>
                    <th className="text-right py-2 font-medium">סטטוס</th>
                    <th className="py-2 pl-1"></th>
                  </tr>
                </thead>
                <tbody>
                  {coupons.map(row => (
                    <tr key={row.id} className="border-b border-gray-100">
                      <td className="py-2 pr-1 font-mono text-xs">{row.carrier}</td>
                      <td className="py-2 font-mono text-xs">
                        {row.code}
                        {row.external_offer_url && (
                          <span className="ml-1 px-1.5 py-0.5 rounded bg-[#fff4d6] text-[#7a5a30] text-[10px] font-sans" title={`קישור חיצוני: ${row.external_offer_url}`}>
                            ↗ {row.partner_name || 'חיצוני'}
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-xs">{row.discount_label || '—'}</td>
                      <td className="py-2 text-xs" dir="ltr">{row.expires_at || '∞'}</td>
                      <td className="py-2">
                        <button onClick={() => handleToggleCouponActive(row)}
                          className={`text-[11px] px-2 py-0.5 rounded-full border ${
                            row.is_active
                              ? 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100'
                              : 'bg-gray-50 text-gray-500 border-gray-200 hover:bg-gray-100'
                          }`}>
                          {row.is_active ? 'פעיל' : 'מבוטל'}
                        </button>
                      </td>
                      <td className="py-2 pl-1 text-left">
                        <div className="flex gap-1 justify-end">
                          <button onClick={() => openCouponForm(row)}
                            className="text-xs text-blue-600 hover:underline">ערוך</button>
                          <span className="text-gray-300">·</span>
                          <button onClick={() => handleDeleteCoupon(row.id)}
                            className="text-xs text-red-600 hover:underline">מחק</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

    </div>
  )
}
