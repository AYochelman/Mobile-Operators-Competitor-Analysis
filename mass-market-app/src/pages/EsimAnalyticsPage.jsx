import { useCallback, useEffect, useState } from 'react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts'
import { api } from '../lib/api'
import { PageHeader } from '../components/moca'
import { useLang } from '../hooks/useLanguage'

/* ────────────────────────────────────────────────────────────────────────
   B2C eSIM traffic dashboard (route: /admin/esim, admin only).
   Funnel for the public compare page: page views → destination picks → deal
   clicks, broken down by day / destination / acquisition source / campaign.
   Views + picks come from esim_events (anonymous beacons); clicks come from
   affiliate_clicks (src='esim'). Data: GET /api/esim/analytics?days=N.
   ──────────────────────────────────────────────────────────────────────── */

const DAY_OPTS = [{ v: 7, l: '7 ימים' }, { v: 30, l: '30 ימים' }, { v: 90, l: '90 ימים' }, { v: 0, l: 'הכל' }]
const nf = (n) => (n == null ? '0' : Number(n).toLocaleString('en-US'))

function StatCard({ label, value, hint, accent }) {
  return (
    <div className="bg-moca-cream rounded-xl p-4">
      <div className="text-xs text-[#8b6b52] font-medium mb-1">{label}</div>
      <div className="text-2xl font-bold" style={{ color: accent || 'var(--color-moca-bolt)' }}>{value}</div>
      {hint && <div className="text-[11px] text-[#a08468] mt-0.5">{hint}</div>}
    </div>
  )
}

function MiniTable({ title, head, rows, empty }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h3 className="font-bold text-sm text-moca-bolt mb-3">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-xs text-gray-400 py-3">{empty}</p>
      ) : (
        <table className="w-full text-sm border-separate border-spacing-y-1">
          <thead>
            <tr className="text-[#8b6b52] text-right text-xs">
              {head.map((h, i) => <th key={i} className={`font-medium pb-1 ${i > 0 ? 'text-left' : ''}`}>{h}</th>)}
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      )}
    </div>
  )
}

export default function EsimAnalyticsPage() {
  const { tt } = useLang()
  const [data, setData] = useState(null)
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const DAY_OPT_LABELS = {
    7: tt('7 ימים', '7 days'), 30: tt('30 ימים', '30 days'),
    90: tt('90 ימים', '90 days'), 0: tt('הכל', 'All'),
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.getEsimAnalytics(days))
    } catch (e) {
      setError(e.message || tt('שגיאה', 'Error'))
    }
    setLoading(false)
  }, [days, tt])

  useEffect(() => { load() }, [load])

  const t = data?.totals || { views: 0, sessions: 0, picks: 0, clicks: 0, conversion: 0 }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <PageHeader kicker="B2C · eSIM" title={tt('דשבורד תנועה', 'Traffic Dashboard')} subtitle={tt('ביקורים, בחירת יעד וקליקים על דילים בעמוד ההשוואה הציבורי', 'Visits, destination picks and deal clicks on the public compare page')} />

      <div className="flex gap-2 my-4 items-center">
        <span className="text-sm text-[#8b6b52] font-medium">{tt('תקופה:', 'Period:')}</span>
        {DAY_OPTS.map(d => (
          <button key={d.v} onClick={() => setDays(d.v)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
              ${days === d.v ? 'bg-moca-bolt text-white border-moca-bolt' : 'bg-white text-moca-bolt border-[#d4bfa8] hover:bg-moca-cream'}`}>
            {DAY_OPT_LABELS[d.v] ?? d.l}
          </button>
        ))}
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3 mb-4">{error}</div>}
      {loading && <p className="text-sm text-gray-400">{tt('טוען…', 'Loading…')}</p>}

      {!loading && data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
            <StatCard label={tt('צפיות בעמוד', 'Page views')} value={nf(t.views)} />
            <StatCard label={tt('סשנים', 'Sessions')} value={nf(t.sessions)} hint={tt('דפדפנים ייחודיים', 'Unique browsers')} />
            <StatCard label={tt('בחירות יעד', 'Destination picks')} value={nf(t.picks)} />
            <StatCard label={tt('קליקים על דילים', 'Deal clicks')} value={nf(t.clicks)} accent="var(--color-moca-hot)" />
            <StatCard label={tt('המרה', 'Conversion')} value={`${t.conversion}%`} hint={tt('קליקים / צפיות', 'Clicks / views')} accent="#4a7c3f" />
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
            <h3 className="font-bold text-sm text-moca-bolt mb-3">{tt('תנועה לפי יום', 'Traffic by day')}</h3>
            {(data.by_day || []).length === 0 ? (
              <p className="text-xs text-gray-400 py-3">{tt('אין נתונים עדיין. ברגע שתגיע תנועה לעמוד, היא תופיע כאן.', 'No data yet. Once traffic reaches the page, it will appear here.')}</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={data.by_day}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="views" name={tt('צפיות', 'Views')} stroke="#5c3317" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="clicks" name={tt('קליקים', 'Clicks')} stroke="#c9622f" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="grid sm:grid-cols-2 gap-4 mb-6">
            <MiniTable
              title={tt('יעדים מובילים', 'Top destinations')} head={[tt('יעד', 'Destination'), tt('בחירות', 'Picks'), tt('קליקים', 'Clicks')]} empty={tt('אין נתונים עדיין', 'No data yet')}
              rows={(data.top_destinations || []).map(r => (
                <tr key={r.destination} className="bg-gray-50">
                  <td className="px-3 py-2 rounded-r-lg font-medium"><bdi>{r.destination}</bdi></td>
                  <td className="px-3 py-2 text-left">{nf(r.picks)}</td>
                  <td className="px-3 py-2 rounded-l-lg text-left text-moca-hot font-medium">{nf(r.clicks)}</td>
                </tr>
              ))}
            />
            <MiniTable
              title={tt('מקור תנועה', 'Traffic source')} head={[tt('מקור', 'Source'), tt('צפיות', 'Views')]} empty={tt('אין נתונים עדיין', 'No data yet')}
              rows={(data.by_source || []).map(r => (
                <tr key={r.src} className="bg-gray-50">
                  <td className="px-3 py-2 rounded-r-lg font-medium"><bdi>{r.src === 'direct' ? tt('ישיר', 'Direct') : r.src}</bdi></td>
                  <td className="px-3 py-2 rounded-l-lg text-left">{nf(r.views)}</td>
                </tr>
              ))}
            />
          </div>

          <MiniTable
            title={tt('לפי קמפיין (פוסט / סרטון)', 'By campaign (post / video)')} head={[tt('קמפיין', 'Campaign'), tt('צפיות', 'Views'), tt('קליקים', 'Clicks'), tt('המרה', 'Conversion')]}
            empty={tt('אין עדיין תנועה מתויגת. הוסיפו ?campaign=… לקישורים בפוסטים כדי לראות איזה תוכן עבד.', 'No tagged traffic yet. Add ?campaign=… to your post links to see which content performed.')}
            rows={(data.by_campaign || []).map(r => {
              const cv = r.views ? `${Math.round((r.clicks / r.views) * 1000) / 10}%` : '-'
              return (
                <tr key={r.campaign} className="bg-gray-50">
                  <td className="px-3 py-2 rounded-r-lg font-medium"><bdi>{r.campaign}</bdi></td>
                  <td className="px-3 py-2 text-left">{nf(r.views)}</td>
                  <td className="px-3 py-2 text-left text-moca-hot font-medium">{nf(r.clicks)}</td>
                  <td className="px-3 py-2 rounded-l-lg text-left text-[#4a7c3f] font-medium">{cv}</td>
                </tr>
              )
            })}
          />

          <p className="text-[11px] text-gray-400 mt-4 leading-relaxed">
            {tt('צפיות ובחירות יעד נאספות אנונימית (ללא PII, IP מגובב) מעמוד ההשוואה. קליקים נמדדים דרך הפניית ה-/go.', 'Views and destination picks are collected anonymously (no PII, hashed IP) from the compare page. Clicks are measured via the /go redirect.')}
            {' '}
            {tt(<>תייגו קישורים בפוסטים עם <code>?campaign=&lt;שם&gt;&utm_source=&lt;פלטפורמה&gt;</code> לפילוח מלא.</>, <>Tag your post links with <code>?campaign=&lt;name&gt;&utm_source=&lt;platform&gt;</code> for full breakdown.</>)}
          </p>
        </>
      )}
    </div>
  )
}
