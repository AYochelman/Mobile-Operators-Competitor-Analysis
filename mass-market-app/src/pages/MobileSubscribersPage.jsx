import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { PageHeader } from '../components/moca'
import { useLang } from '../hooks/useLanguage'
import { carrierLabel } from '../data/carrierLabels'

/* ────────────────────────────────────────────────────────────────────────
   /mobile-deals reminder subscribers (route: /admin/mobile-subscribers,
   super-admin only). Every email / phone number consumers left in the
   ReminderModal, with the plan they track, their declared actual price and
   the delivery state. Data: GET /api/mobile/reminders/subscribers
   (contact details — served only behind super-admin auth).
   ──────────────────────────────────────────────────────────────────────── */

const nf = (n) => (n == null ? '0' : Number(n).toLocaleString('en-US'))

function StatCard({ label, value, hint }) {
  return (
    <div className="bg-moca-cream rounded-xl p-4">
      <div className="text-xs text-[#8b6b52] font-medium mb-1">{label}</div>
      <div className="text-2xl font-bold text-moca-bolt">{value}</div>
      {hint && <div className="text-[11px] text-[#a08468] mt-0.5">{hint}</div>}
    </div>
  )
}

export default function MobileSubscribersPage() {
  const { tt } = useLang()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [kind, setKind] = useState('all')
  const [q, setQ] = useState('')

  useEffect(() => {
    let alive = true
    api.getMobileSubscribers()
      .then((d) => { if (alive) setData(d) })
      .catch((e) => { if (alive) setError(e.message || 'error') })
    return () => { alive = false }
  }, [])

  const KIND_LABELS = {
    better_deal: tt('חבילה משתלמת יותר', 'Better deal'),
    plan_end: tt('סיום מסלול', 'Plan end'),
  }
  const CHANNEL_LABELS = {
    email: tt('מייל', 'Email'), whatsapp: tt('וואטסאפ', 'WhatsApp'), both: tt('מייל + וואטסאפ', 'Both'),
  }

  const rows = useMemo(() => {
    let out = data?.rows || []
    if (kind !== 'all') out = out.filter((r) => r.kind === kind)
    const needle = q.trim().toLowerCase()
    if (needle) {
      out = out.filter((r) =>
        (r.email || '').toLowerCase().includes(needle)
        || (r.phone || '').includes(needle)
        || (r.plan_name || '').toLowerCase().includes(needle)
        || carrierLabel(r.carrier).toLowerCase().includes(needle))
    }
    return out
  }, [data, kind, q])

  const fmtDate = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    return Number.isNaN(+d) ? '' : d.toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: '2-digit' })
  }

  const statusOf = (r) => {
    if (r.kind === 'plan_end') {
      if (r.followup_sent) return tt('נשלח + פולו-אפ', 'Sent + follow-up')
      if (r.done) return tt('תזכורת נשלחה', 'Reminder sent')
      return tt('ממתין', 'Pending')
    }
    return r.last_notified_at
      ? tt('התראה נשלחה', 'Alerted') + ' · ' + fmtDate(r.last_notified_at)
      : tt('פעיל, טרם נשלח', 'Active, none yet')
  }

  const exportCsv = () => {
    const head = ['created_at', 'kind', 'email', 'phone', 'channel', 'carrier', 'plan_name',
      'price', 'paid_price', 'end_date', 'remind_days_before', 'lang', 'done', 'last_notified_at']
    const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
    const lines = [head.join(',')]
    for (const r of rows) lines.push(head.map((h) => esc(r[h])).join(','))
    const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `moca-mobile-subscribers-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const s = data?.stats || {}

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <PageHeader kicker="B2C · Mobile" title={tt('מנויי תזכורות', 'Reminder subscribers')}
        subtitle={tt('כל המיילים והמספרים שהושארו בדף השוואת המסלולים - למעקב, לשירות וליצוא', 'Every email and phone number left on the plan-comparison page - for tracking, service and export')} />

      {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3 my-4">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 my-4">
        <StatCard label={tt('הרשמות פעילות', 'Active signups')} value={nf(s.active_rows)} />
        <StatCard label={tt('סה"כ הרשמות', 'Total signups')} value={nf(s.total_rows)} />
        <StatCard label={tt('מיילים ייחודיים', 'Unique emails')} value={nf(s.unique_emails)} />
        <StatCard label={tt('מספרים ייחודיים', 'Unique phones')} value={nf(s.unique_phones)} />
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        {['all', 'better_deal', 'plan_end'].map((k) => (
          <button key={k} onClick={() => setKind(k)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
              ${kind === k ? 'bg-moca-bolt text-white border-moca-bolt' : 'bg-white text-moca-bolt border-[#d4bfa8] hover:bg-moca-cream'}`}>
            {k === 'all' ? tt('הכול', 'All') : KIND_LABELS[k]}
          </button>
        ))}
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={tt('חיפוש מייל / מספר / חבילה…', 'Search email / phone / plan…')}
          className="flex-1 min-w-[180px] text-sm border border-[#d4bfa8] rounded-full px-4 py-1.5 outline-none focus:border-moca-bolt bg-white" />
        <button onClick={exportCsv} disabled={!rows.length}
          className="px-4 py-1.5 rounded-full text-xs font-bold bg-moca-bolt text-white disabled:opacity-50">
          {tt('יצוא CSV', 'Export CSV')} ({rows.length})
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
        {data === null && !error ? (
          <p className="text-sm text-gray-400 p-6 text-center">{tt('טוען…', 'Loading…')}</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-gray-400 p-6 text-center">{tt('אין עדיין הרשמות', 'No signups yet')}</p>
        ) : (
          <table className="w-full text-sm min-w-[900px]">
            <thead>
              <tr className="text-[#8b6b52] text-right text-xs border-b border-gray-100">
                {[tt('נרשם', 'Created'), tt('סוג', 'Kind'), tt('מייל', 'Email'), tt('נייד', 'Phone'),
                  tt('ערוץ', 'Channel'), tt('חבילה', 'Plan'), tt('מחיר מחירון', 'List price'),
                  tt('משלם בפועל', 'Pays'), tt('סיום מסלול', 'Term end'), tt('סטטוס', 'Status')]
                  .map((h, i) => <th key={i} className="font-medium px-3 py-2 whitespace-nowrap">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-moca-mist">
                  <td className="px-3 py-2 whitespace-nowrap text-xs text-[#8b6b52]">{fmtDate(r.created_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-xs font-medium">{KIND_LABELS[r.kind] || r.kind}</td>
                  <td className="px-3 py-2 whitespace-nowrap" dir="ltr">{r.email || <span className="text-gray-300">-</span>}</td>
                  <td className="px-3 py-2 whitespace-nowrap" dir="ltr">{r.phone ? `+${r.phone}` : <span className="text-gray-300">-</span>}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-xs">{CHANNEL_LABELS[r.channel] || r.channel}</td>
                  <td className="px-3 py-2">
                    <span className="font-medium">{carrierLabel(r.carrier)}</span>
                    <span className="text-xs text-[#8b6b52]"> · {r.plan_name}</span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap" dir="ltr">{r.price != null ? `₪${r.price}` : '-'}</td>
                  <td className="px-3 py-2 whitespace-nowrap font-medium" dir="ltr">
                    {r.paid_price != null ? `₪${r.paid_price}` : <span className="text-gray-300">-</span>}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-xs">
                    {r.end_date ? `${fmtDate(r.end_date)} (${r.remind_days_before}${tt(' ימים לפני', 'd before')})` : '-'}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-xs">{statusOf(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-[11px] text-[#a08468] mt-3 leading-relaxed">
        {tt('פרטי הקשר נמסרו בהסכמה לצורך התזכורות בלבד (מדיניות פרטיות, סעיף 3א). שימוש אחר בפרטים מחייב בסיס הסכמה נפרד.',
            'Contact details were given with consent for reminders only (privacy policy, section 3a). Any other use requires a separate consent basis.')}
      </p>
    </div>
  )
}
