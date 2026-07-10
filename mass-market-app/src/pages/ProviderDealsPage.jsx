import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { api } from '../lib/api'

// ── Status vocab ────────────────────────────────────────────────────────────
const GREEN = 'var(--color-moca-down)'   // #4a7c3f — good / done
const AMBER = 'var(--color-moca-hot)'    // #c9622f — in progress / attention
const RED   = 'var(--color-moca-up)'     // #b4472d — leak / bad
const MUTED = 'var(--color-moca-muted)'
const BLUE  = 'var(--color-moca-bolt)'

const OUTREACH = {
  live:          { label: 'חי',          color: GREEN },
  approved:      { label: 'אושר',        color: GREEN },
  in_discussion: { label: 'במו״מ',       color: AMBER },
  contacted:     { label: 'פנינו',       color: BLUE  },
  declined:      { label: 'נדחה',        color: MUTED },
  not_contacted: { label: 'לא פנינו',    color: MUTED },
}
const AGREEMENT = {
  live:    { label: 'הסכם חי',  color: GREEN },
  signed:  { label: 'נחתם',     color: GREEN },
  pending: { label: 'בתהליך',   color: AMBER },
  none:    { label: 'אין',      color: MUTED },
}
const PRIORITY = {
  high: { label: 'גבוהה', color: RED },
  med:  { label: 'בינונית', color: AMBER },
  low:  { label: 'נמוכה',  color: MUTED },
}

const FILTERS = [
  { key: 'all',      label: 'הכל' },
  { key: 'action',   label: 'דורש פעולה' },
  { key: 'live',     label: 'חי ומרוויח' },
  { key: 'leak',     label: 'דליפות' },
  { key: 'pipeline', label: 'בתהליך' },
]

function fmtDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleDateString('he-IL', { day: 'numeric', month: 'short', year: '2-digit' })
  } catch { return iso }
}
function fmtRelative(iso) {
  if (!iso) return '-'
  try {
    const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
    if (min < 1)  return 'הרגע'
    if (min < 60) return `לפני ${min} דק׳`
    const hrs = Math.floor(min / 60)
    if (hrs < 24) return `לפני ${hrs} שע׳`
    return fmtDate(iso)
  } catch { return fmtDate(iso) }
}

// A deal is "live & earning" only when a live coupon / tracking link actually
// credits us — a leak (e.g. third-party coupons) explicitly does NOT count.
const isEarning = (d) => !d.is_leak && (d.coupon_live || d.has_tracking_link) &&
  (d.agreement_status === 'live' || d.agreement_status === 'signed')
const needsAction = (d) => d.is_leak || d.priority === 'high'
const inPipeline = (d) => !isEarning(d) && !d.is_leak &&
  ['contacted', 'in_discussion', 'approved'].includes(d.outreach_status)

function Pill({ label, color, solid }) {
  return (
    <span
      className="inline-block px-2 py-0.5 rounded-full text-[11px] font-bold whitespace-nowrap"
      style={solid
        ? { background: color, color: '#fff' }
        : { background: 'var(--color-moca-cream)', color }}
    >
      {label}
    </span>
  )
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="rounded-xl border border-moca-border bg-white p-4">
      <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: MUTED }}>{label}</div>
      <div className="mt-1 text-2xl font-bold" style={{ color: accent || 'var(--color-moca-dark)' }}>{value}</div>
      {sub && <div className="mt-1 text-xs" style={{ color: 'var(--color-moca-sub)' }}>{sub}</div>}
    </div>
  )
}

// Coupon cell — the "is there a coupon in the air, and if not why" answer.
function CouponCell({ d }) {
  if (d.is_leak && d.coupon_live) {
    return (
      <div className="text-xs">
        <Pill label={`⚠ ${d.coupon_code}`} color={RED} solid />
        <div className="mt-0.5 truncate max-w-[220px]" style={{ color: RED }} title={d.coupon_note}>
          {d.coupon_note || 'קופון צד-ג׳ (לא מזכה אותנו)'}
        </div>
      </div>
    )
  }
  if (d.coupon_live) {
    return (
      <div className="text-xs">
        <span className="font-bold tnum" style={{ color: GREEN }}>{d.coupon_code}</span>
        {d.coupon_discount && <span style={{ color: 'var(--color-moca-sub)' }}> · {d.coupon_discount}</span>}
      </div>
    )
  }
  return (
    <div className="text-xs">
      <span style={{ color: MUTED }}>אין</span>
      {d.coupon_note && (
        <div className="mt-0.5 truncate max-w-[220px]" style={{ color: 'var(--color-moca-sub)' }} title={d.coupon_note}>
          {d.coupon_note}
        </div>
      )}
    </div>
  )
}

export default function ProviderDealsPage() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [filter, setFilter]   = useState('all')
  const [open, setOpen]       = useState(null)      // provider_id of open detail modal
  const [fetchedAt, setFetchedAt] = useState(null)
  const [, force]             = useState(0)         // tick for the "updated ago" label
  const firstLoad = useRef(true)

  const load = useCallback(async () => {
    if (firstLoad.current) setLoading(true)
    setError(null)
    try {
      const d = await api.getProviderDeals()
      setData(d)
      setFetchedAt(Date.now())
    } catch (e) {
      setError(e.message || 'שגיאה')
    } finally {
      setLoading(false)
      firstLoad.current = false
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Auto-refresh: poll every 60s + refetch when the tab regains focus.
  useEffect(() => {
    const iv = setInterval(load, 60000)
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => { clearInterval(iv); window.removeEventListener('focus', onFocus) }
  }, [load])

  // Re-render the "updated ago" label once a minute.
  useEffect(() => {
    const t = setInterval(() => force(n => n + 1), 30000)
    return () => clearInterval(t)
  }, [])

  const deals = data?.deals || []

  const summary = useMemo(() => {
    let contacted = 0, coupons = 0, signed = 0, action = 0, leaks = 0
    let commSum = 0, commN = 0
    for (const d of deals) {
      if (d.outreach_status && d.outreach_status !== 'not_contacted') contacted++
      if (d.coupon_live && !d.is_leak) coupons++
      if (d.agreement_status === 'signed' || d.agreement_status === 'live') signed++
      if (needsAction(d)) action++
      if (d.is_leak) leaks++
      if (isEarning(d) && typeof d.commission_pct === 'number') { commSum += d.commission_pct; commN++ }
    }
    return {
      total: deals.length, contacted, coupons, signed, action, leaks,
      avgComm: commN ? Math.round(commSum / commN) : null,
    }
  }, [deals])

  const filtered = useMemo(() => {
    switch (filter) {
      case 'action':   return deals.filter(needsAction)
      case 'live':     return deals.filter(isEarning)
      case 'leak':     return deals.filter(d => d.is_leak)
      case 'pipeline': return deals.filter(inPipeline)
      default:         return deals
    }
  }, [deals, filter])

  const openDeal = open ? deals.find(d => d.provider_id === open) : null

  if (loading) {
    return <div className="p-6 text-sm" style={{ color: MUTED }}>טוען…</div>
  }
  if (error) {
    return <div className="p-6 text-sm text-red-600">שגיאה: {error}</div>
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--color-moca-dark)', fontFamily: 'var(--font-display)' }}>
            סטטוס ספקים
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--color-moca-sub)' }}>
            פנייה, קופון באוויר, הסכם + אחוז עמלה, ופעולות נדרשות - לכל ספק. הקופונים מתעדכנים חי מה-DB.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: MUTED }}>
          <span>עודכן {fmtRelative(fetchedAt)}</span>
          <button
            onClick={load}
            className="px-3 py-1.5 rounded-lg font-semibold border border-moca-border"
            style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
            title="רענן"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <StatCard label="ספקים" value={summary.total} />
        <StatCard label="פנינו" value={summary.contacted} sub={`מתוך ${summary.total}`} />
        <StatCard label="קופון חי" value={summary.coupons} sub="שלנו, מזכה" accent={GREEN} />
        <StatCard label="הסכם סגור" value={summary.signed} accent={GREEN} />
        <StatCard label="עמלה ממוצעת" value={summary.avgComm != null ? `${summary.avgComm}%` : '-'} sub="בעסקאות חיות" />
        <StatCard label="דורש פעולה" value={summary.action} accent={summary.action ? AMBER : undefined} />
        <StatCard label="דליפות" value={summary.leaks} sub="ממומן אך 0₪" accent={summary.leaks ? RED : GREEN} />
      </div>

      {/* Filter chips */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {FILTERS.map(f => {
          const active = filter === f.key
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
              style={{
                background: active ? BLUE : 'var(--color-moca-cream)',
                color:      active ? '#fff' : 'var(--color-moca-text)',
                border:     '1px solid var(--color-moca-border)',
              }}
            >
              {f.label}
            </button>
          )
        })}
      </div>

      {/* Table */}
      <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
        {filtered.length === 0 ? (
          <p className="text-sm p-6 text-center" style={{ color: MUTED }}>אין ספקים בקטגוריה זו</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[920px]">
              <thead style={{ background: 'var(--color-moca-mist)' }}>
                <tr>
                  {['ספק', 'פנייה', 'קופון באוויר', 'הסכם / עמלה', 'קליקים 30ׁ', 'עדיפות', 'פעולה נדרשת'].map((h, i) => (
                    <th key={i} className={`px-3 py-2 text-xs font-semibold whitespace-nowrap ${i >= 4 && i <= 5 ? 'text-center' : 'text-start'}`} style={{ color: MUTED }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(d => {
                  const o = OUTREACH[d.outreach_status] || OUTREACH.not_contacted
                  const a = AGREEMENT[d.agreement_status] || AGREEMENT.none
                  const p = PRIORITY[d.priority] || PRIORITY.low
                  return (
                    <tr
                      key={d.provider_id}
                      onClick={() => setOpen(d.provider_id)}
                      className="border-t border-moca-border cursor-pointer hover:bg-moca-mist"
                      style={d.is_leak ? { boxShadow: `inset 3px 0 0 ${RED}` } : undefined}
                    >
                      {/* Provider */}
                      <td className="px-3 py-2.5 text-start">
                        <div className="font-semibold flex items-center gap-1.5" style={{ color: 'var(--color-moca-text)' }}>
                          {d.display_name}
                          {d.is_israeli && <span title="ישראלי">🇮🇱</span>}
                        </div>
                        <div className="text-[11px]" style={{ color: MUTED }}>{d.program_network || '-'}</div>
                      </td>
                      {/* Outreach */}
                      <td className="px-3 py-2.5 text-start">
                        <Pill label={o.label} color={o.color} />
                        <div className="text-[11px] mt-0.5" style={{ color: MUTED }}>{fmtDate(d.outreach_last_at)}</div>
                      </td>
                      {/* Coupon */}
                      <td className="px-3 py-2.5 text-start"><CouponCell d={d} /></td>
                      {/* Agreement + commission */}
                      <td className="px-3 py-2.5 text-start">
                        <Pill label={a.label} color={a.color} />
                        <div className="text-[11px] mt-0.5 tnum" style={{ color: 'var(--color-moca-sub)' }}>
                          {typeof d.commission_pct === 'number' ? `${d.commission_pct}%` : (d.commission_note ? '' : '-')}
                          {d.commission_note && <span> {d.commission_note.length > 28 ? d.commission_note.slice(0, 28) + '…' : d.commission_note}</span>}
                        </div>
                      </td>
                      {/* Clicks */}
                      <td className="px-3 py-2.5 text-center tnum" style={{ color: d.clicks_30d ? 'var(--color-moca-text)' : MUTED }}>
                        {d.clicks_30d || 0}
                      </td>
                      {/* Priority */}
                      <td className="px-3 py-2.5 text-center"><Pill label={p.label} color={p.color} /></td>
                      {/* Next action */}
                      <td className="px-3 py-2.5 text-start text-xs max-w-[280px]" style={{ color: 'var(--color-moca-text)' }}>
                        <div className="line-clamp-2" title={d.next_actions}>{d.next_actions || '-'}</div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="text-[11px]" style={{ color: MUTED }}>
        הנתונים מתוחזקים ב-<code>seed_provider_deals.py</code> (מריצים מחדש לעדכון). מצב קופונים וקליקים חיים מה-DB.
      </p>

      {/* Detail modal */}
      {openDeal && (
        <div
          className="fixed inset-0 z-[9000] flex items-center justify-center p-4"
          style={{ background: 'rgba(40,30,15,0.35)' }}
          onClick={() => setOpen(null)}
        >
          <div
            className="bg-white rounded-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto"
            style={{ boxShadow: 'var(--sh-modal)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="px-5 py-4 border-b border-moca-border flex items-start justify-between gap-3 sticky top-0 bg-white">
              <div>
                <div className="text-lg font-bold flex items-center gap-2" style={{ color: 'var(--color-moca-dark)' }}>
                  {openDeal.display_name}
                  {openDeal.is_israeli && <span>🇮🇱</span>}
                  {openDeal.is_leak && <Pill label="דליפה" color={RED} solid />}
                </div>
                <div className="text-xs mt-0.5" style={{ color: MUTED }}>{openDeal.program_network || '-'}</div>
              </div>
              <button onClick={() => setOpen(null)} className="text-2xl leading-none px-2" style={{ color: MUTED }} aria-label="סגור">×</button>
            </div>
            <div className="p-5 space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <Field label="פנייה">
                  <Pill label={(OUTREACH[openDeal.outreach_status] || OUTREACH.not_contacted).label} color={(OUTREACH[openDeal.outreach_status] || OUTREACH.not_contacted).color} />
                  <span className="text-xs mr-1.5" style={{ color: MUTED }}>{fmtDate(openDeal.outreach_last_at)}</span>
                </Field>
                <Field label="הסכם">
                  <Pill label={(AGREEMENT[openDeal.agreement_status] || AGREEMENT.none).label} color={(AGREEMENT[openDeal.agreement_status] || AGREEMENT.none).color} />
                </Field>
                <Field label="עמלה שלנו">
                  <span style={{ color: 'var(--color-moca-text)' }}>
                    {typeof openDeal.commission_pct === 'number' ? `${openDeal.commission_pct}%` : ''}
                    {openDeal.commission_note ? ` ${openDeal.commission_note}` : (typeof openDeal.commission_pct !== 'number' ? '-' : '')}
                  </span>
                </Field>
                <Field label="קליקים (30 יום)">
                  <span className="tnum" style={{ color: 'var(--color-moca-text)' }}>{openDeal.clicks_30d || 0}</span>
                </Field>
                <Field label="לינק tracking">
                  <span style={{ color: openDeal.has_tracking_link ? GREEN : MUTED }}>
                    {openDeal.has_tracking_link ? 'מחובר ✓' : 'לא מחובר'}
                  </span>
                </Field>
                <Field label="עדיפות">
                  <Pill label={(PRIORITY[openDeal.priority] || PRIORITY.low).label} color={(PRIORITY[openDeal.priority] || PRIORITY.low).color} />
                </Field>
              </div>

              <Field label="קופון באוויר" block>
                <CouponCell d={openDeal} />
              </Field>

              <Field label="פעולה נדרשת" block>
                <p style={{ color: 'var(--color-moca-text)' }}>{openDeal.next_actions || '-'}</p>
              </Field>

              {openDeal.contact && (
                <Field label="איש קשר" block>
                  <span style={{ color: 'var(--color-moca-text)' }}>{openDeal.contact}</span>
                </Field>
              )}
              {openDeal.notes && (
                <Field label="הערות" block>
                  <p className="text-xs" style={{ color: 'var(--color-moca-sub)' }}>{openDeal.notes}</p>
                </Field>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, children, block }) {
  return (
    <div className={block ? '' : ''}>
      <div className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: MUTED }}>{label}</div>
      <div>{children}</div>
    </div>
  )
}
