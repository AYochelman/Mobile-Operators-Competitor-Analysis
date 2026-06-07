import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../lib/api'
import { ROUTE_META } from '../components/moca/routeMeta'

const WINDOWS = [
  { label: '7 ימים',  days: 7 },
  { label: '30 ימים', days: 30 },
  { label: '90 ימים', days: 90 },
]

const ROLE_LABELS = { admin: 'מנהל', viewer: 'צופה', super_admin: 'מנהל-על' }

// Gender-neutral noun phrases (Hebrew verbs inflect for gender; nouns don't).
const EVENT_LABELS = {
  login:             'התחברות',
  page_view:         'צפייה בעמוד',
  alert_created:     'יצירת התראה',
  watchlist_added:   'הוספה למעקב',
  watchlist_removed: 'הסרה ממעקב',
  comparison_saved:  'שמירת השוואה',
  chat_used:         'שימוש בצ׳אט AI',
  annotation_added:  'הוספת הערת צוות',
  search:            'חיפוש',
  export:            'ייצוא לאקסל',
}

// pathname → Hebrew page name (reuse the Topbar route map)
const PATH_LABELS = ROUTE_META.reduce((m, r) => { m[r.match] = r.title; return m }, {})
function pageLabel(path) {
  if (!path) return '—'
  if (PATH_LABELS[path]) return PATH_LABELS[path]
  const base = path.split('?')[0].split('#')[0]
  return PATH_LABELS[base] || path
}

function detailSummary(details) {
  if (!details) return ''
  try {
    const d = JSON.parse(details)
    if (d.q != null)                 return `"${d.q}"`
    if (d.carrier && d.plan_name)    return `${d.carrier} · ${d.plan_name}`
    if (d.carrier && d.plan_pattern) return `${d.carrier} · ${d.plan_pattern}`
    if (d.carrier)                   return d.carrier
    if (d.name)                      return `${d.name}${d.count != null ? ` · ${d.count} חבילות` : ''}`
    if (d.tab)                       return `${d.tab}${d.count != null ? ` · ${d.count}` : ''}`
    if (d.model)                     return d.model
    return ''
  } catch {
    return ''
  }
}

function fmtNum(n) {
  if (!n) return '0'
  try { return new Intl.NumberFormat('he-IL').format(n) } catch { return String(n) }
}

function fmtDateTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('he-IL', {
      day: '2-digit', month: '2-digit', year: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('he-IL', { day: 'numeric', month: 'short', year: '2-digit' })
  } catch { return iso }
}

function fmtRelative(iso) {
  if (!iso) return 'אף פעם'
  try {
    const diffMs = Date.now() - new Date(iso).getTime()
    const min = Math.floor(diffMs / 60000)
    if (min < 1)  return 'הרגע'
    if (min < 60) return `לפני ${min} דק׳`
    const hrs = Math.floor(min / 60)
    if (hrs < 24) return `לפני ${hrs} שע׳`
    const days = Math.floor(hrs / 24)
    if (days < 30) return `לפני ${days} ימים`
    return fmtDate(iso)
  } catch { return fmtDate(iso) }
}

const pctOf = (n, d) => (d > 0 ? Math.round((n / d) * 100) : 0)

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-moca-border bg-white p-4">
      <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold" style={{ color: 'var(--color-moca-dark)' }}>
        {value}
      </div>
      {sub && (
        <div className="mt-1 text-xs" style={{ color: 'var(--color-moca-sub)' }}>
          {sub}
        </div>
      )}
    </div>
  )
}

function RoleBadge({ role }) {
  const color = role === 'admin' ? 'var(--color-moca-bolt)' : 'var(--color-moca-sub)'
  return (
    <span
      className="inline-block px-2 py-0.5 rounded-full text-[11px] font-bold whitespace-nowrap"
      style={{ background: 'var(--color-moca-cream)', color }}
    >
      {ROLE_LABELS[role] || role}
    </span>
  )
}

// Sortable table header cell.
function Th({ label, sortField, sortKey, sortDir, onSort, align = 'end' }) {
  const active = sortKey === sortField
  return (
    <th
      onClick={() => onSort(sortField)}
      className={`px-3 py-2 text-${align} text-xs font-semibold cursor-pointer select-none whitespace-nowrap`}
      style={{ color: active ? 'var(--color-moca-bolt)' : 'var(--color-moca-muted)' }}
      title="מיון"
    >
      {label}{active ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
    </th>
  )
}

export default function UserActivityPage() {
  const [days, setDays]       = useState(30)
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  const [sortKey, setSortKey] = useState('last_seen')
  const [sortDir, setSortDir] = useState('desc')

  const [openEmail, setOpenEmail]         = useState(null)
  const [events, setEvents]               = useState([])
  const [eventsLoading, setEventsLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const d = await api.getActivityOverview(days)
      setData(d)
    } catch (e) {
      setError(e.message || 'שגיאה')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  // Drill-down: load a single user's recent event feed.
  useEffect(() => {
    if (!openEmail) return
    let alive = true
    setEventsLoading(true); setEvents([])
    api.getActivityEvents({ email: openEmail, days, limit: 100 })
      .then(r => { if (alive) setEvents(r.events || []) })
      .catch(() => { if (alive) setEvents([]) })
      .finally(() => { if (alive) setEventsLoading(false) })
    return () => { alive = false }
  }, [openEmail, days])

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  const summary = data?.summary || {}
  const users   = data?.users || []

  const sortedUsers = useMemo(() => {
    const dateKeys = new Set(['last_seen', 'created_at', 'last_sign_in_at'])
    const strKeys  = new Set(['email', 'role', 'workspace_name'])
    const arr = [...users]
    arr.sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey]
      if (dateKeys.has(sortKey)) {
        av = av ? new Date(av).getTime() : 0
        bv = bv ? new Date(bv).getTime() : 0
        return sortDir === 'asc' ? av - bv : bv - av
      }
      if (strKeys.has(sortKey)) {
        av = (av || '').toString().toLowerCase()
        bv = (bv || '').toString().toLowerCase()
        return sortDir === 'asc' ? av.localeCompare(bv, 'he') : bv.localeCompare(av, 'he')
      }
      av = av || 0; bv = bv || 0
      return sortDir === 'asc' ? av - bv : bv - av
    })
    return arr
  }, [users, sortKey, sortDir])

  const chartData = useMemo(
    () => (summary.by_day || []).map(d => ({ day: (d.day || '').slice(5), events: d.events, users: d.users })),
    [summary],
  )

  // Activation funnel, retention buckets, and feature adoption — derived from
  // the windowed users array. "Logged in"/"never" use Supabase last_sign_in_at
  // (lifetime); actions use the selected window.
  const analytics = useMemo(() => {
    const now = Date.now(); const DAY = 86400000
    let loggedIn = 0, activated = 0, never = 0, active7 = 0, dormant = 0
    let wPages = 0, wAlerts = 0, wWatch = 0, wCompare = 0, wChat = 0
    for (const u of users) {
      const lastTouch = Math.max(
        u.last_sign_in_at ? new Date(u.last_sign_in_at).getTime() : 0,
        u.last_seen ? new Date(u.last_seen).getTime() : 0,
      )
      if (!u.last_sign_in_at) never++; else loggedIn++
      if (((u.alerts_created || 0) + (u.watchlist_added || 0) + (u.comparisons_saved || 0) + (u.chat_used || 0)) > 0) activated++
      if ((u.page_views || 0) > 0) wPages++
      if ((u.alerts_created || 0) > 0) wAlerts++
      if ((u.watchlist_added || 0) > 0) wWatch++
      if ((u.comparisons_saved || 0) > 0) wCompare++
      if ((u.chat_used || 0) > 0) wChat++
      if (lastTouch && now - lastTouch <= 7 * DAY) active7++
      else if (u.last_sign_in_at && lastTouch && now - lastTouch > 14 * DAY) dormant++
    }
    const total = users.length
    return {
      funnel: { registered: total, loggedIn, activated },
      buckets: { active7, dormant, never },
      adoption: [
        { key: 'page', label: 'גלישה בעמודים', n: wPages,   pct: pctOf(wPages, total) },
        { key: 'alert', label: 'התראות',        n: wAlerts,  pct: pctOf(wAlerts, total) },
        { key: 'watch', label: 'מעקב חבילות',   n: wWatch,   pct: pctOf(wWatch, total) },
        { key: 'comp',  label: 'השוואות',        n: wCompare, pct: pctOf(wCompare, total) },
        { key: 'chat',  label: 'צ׳אט AI',        n: wChat,    pct: pctOf(wChat, total) },
      ],
    }
  }, [users])

  const workspaceRollup = useMemo(() => {
    const map = new Map()
    for (const u of users) {
      const name = u.workspace_name || '— ללא Workspace'
      const g = map.get(name) || { name, users: 0, active: 0, logins: 0, page_views: 0, actions: 0 }
      g.users += 1
      if (u.last_seen) g.active += 1
      g.logins += u.logins || 0
      g.page_views += u.page_views || 0
      g.actions += (u.alerts_created || 0) + (u.watchlist_added || 0) + (u.comparisons_saved || 0) + (u.chat_used || 0)
      map.set(name, g)
    }
    return [...map.values()].sort((a, b) => b.page_views - a.page_views)
  }, [users])

  const dau = summary.active_today || 0
  const wau = summary.active_this_week || 0
  const mau = summary.active_this_month || 0
  const stickiness = pctOf(dau, mau)

  if (loading) {
    return <div className="p-6 text-sm" style={{ color: 'var(--color-moca-muted)' }}>טוען…</div>
  }
  if (error) {
    return <div className="p-6 text-sm text-red-600">שגיאה: {error}</div>
  }

  const { funnel, buckets, adoption } = analytics

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header: management link + description + window selector */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            to="/settings?tab=users"
            className="px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap"
            style={{ background: 'var(--color-moca-bolt)', color: '#fff' }}
          >
            ניהול משתמשים
          </Link>
          <p className="text-sm" style={{ color: 'var(--color-moca-sub)' }}>
            מעקב פעילות לקוחות — התחברויות, עמודים שנצפו ופעולות. מנהלי-על אינם נספרים.
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {WINDOWS.map((w) => (
            <button
              key={w.days}
              onClick={() => setDays(w.days)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
              style={{
                background: days === w.days ? 'var(--color-moca-bolt)' : 'var(--color-moca-cream)',
                color:      days === w.days ? '#fff'                  : 'var(--color-moca-text)',
                border:     '1px solid var(--color-moca-border)',
              }}
            >
              {w.label}
            </button>
          ))}
          <button
            onClick={load}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-moca-border"
            style={{ color: 'var(--color-moca-sub)', background: 'var(--color-moca-mist)' }}
            title="רענן"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Stat cards — active-user funnel by recency (DAU / WAU / MAU) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="סך משתמשים" value={fmtNum(summary.total_users)} sub="לקוחות (ללא מנהלי-על)" />
        <StatCard label="פעילים היום" value={fmtNum(dau)} sub="DAU" />
        <StatCard label="פעילים השבוע" value={fmtNum(wau)} sub="WAU" />
        <StatCard label="פעילים החודש" value={fmtNum(mau)} sub={mau > 0 ? `MAU · דביקות ${stickiness}%` : 'MAU'} />
      </div>

      {/* Activation funnel + retention buckets */}
      <div className="rounded-xl border border-moca-border bg-white p-4">
        <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--color-moca-dark)' }}>
          אקטיבציה ושימור <span className="font-normal text-xs" style={{ color: 'var(--color-moca-muted)' }}>(פעולות בטווח הנבחר)</span>
        </h3>
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg p-3 text-center" style={{ background: 'var(--color-moca-mist)' }}>
            <div className="text-2xl font-bold" style={{ color: 'var(--color-moca-dark)' }}>{fmtNum(funnel.registered)}</div>
            <div className="text-xs mt-0.5" style={{ color: 'var(--color-moca-sub)' }}>נרשמו</div>
          </div>
          <div className="rounded-lg p-3 text-center" style={{ background: 'var(--color-moca-mist)' }}>
            <div className="text-2xl font-bold" style={{ color: 'var(--color-moca-dark)' }}>{fmtNum(funnel.loggedIn)}</div>
            <div className="text-xs mt-0.5" style={{ color: 'var(--color-moca-sub)' }}>התחברו · {pctOf(funnel.loggedIn, funnel.registered)}%</div>
          </div>
          <div className="rounded-lg p-3 text-center" style={{ background: 'var(--color-moca-mist)' }}>
            <div className="text-2xl font-bold" style={{ color: 'var(--color-moca-dark)' }}>{fmtNum(funnel.activated)}</div>
            <div className="text-xs mt-0.5" style={{ color: 'var(--color-moca-sub)' }}>ביצעו פעולה · {pctOf(funnel.activated, funnel.registered)}%</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: 'var(--color-moca-cream)', color: 'var(--color-moca-down)' }}>
            פעילים (7 ימים): {fmtNum(buckets.active7)}
          </span>
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: 'var(--color-moca-cream)', color: 'var(--color-moca-up)' }}>
            רדומים (14+ ימים): {fmtNum(buckets.dormant)}
          </span>
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: 'var(--color-moca-cream)', color: 'var(--color-moca-muted)' }}>
            נרשמו ולא התחברו: {fmtNum(buckets.never)}
          </span>
        </div>
      </div>

      {/* Daily activity chart */}
      <div className="rounded-xl border border-moca-border bg-white p-4">
        <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--color-moca-dark)' }}>
          פעילות יומית
        </h3>
        {chartData.length === 0 ? (
          <p className="text-sm py-8 text-center" style={{ color: 'var(--color-moca-muted)' }}>
            עדיין אין נתוני פעילות. ברגע שלקוחות יתחברו ויגלשו, האירועים יירשמו כאן אוטומטית.
          </p>
        ) : (
          <div style={{ width: '100%', height: 260, direction: 'ltr' }}>
            <ResponsiveContainer>
              <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-moca-border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--color-moca-sub)' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--color-moca-sub)' }} />
                <Tooltip
                  formatter={(v, name) => name === 'users' ? [v, 'משתמשים פעילים'] : [v, 'אירועים']}
                  labelFormatter={(l) => `יום ${l}`}
                  contentStyle={{
                    background: '#fff',
                    border: '1px solid var(--color-moca-border)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="events" fill="var(--color-moca-bolt)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Feature adoption */}
      <div className="rounded-xl border border-moca-border bg-white p-4">
        <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--color-moca-dark)' }}>
          אימוץ פיצ׳רים <span className="font-normal text-xs" style={{ color: 'var(--color-moca-muted)' }}>(% מהמשתמשים שהשתמשו, בטווח)</span>
        </h3>
        <div className="space-y-2.5">
          {adoption.map((a) => (
            <div key={a.key} className="flex items-center gap-3">
              <div className="w-28 text-sm text-start shrink-0" style={{ color: 'var(--color-moca-text)' }}>{a.label}</div>
              <div className="flex-1 h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--color-moca-cream)' }}>
                <div className="h-full rounded-full" style={{ width: `${a.pct}%`, background: 'var(--color-moca-bolt)' }} />
              </div>
              <div className="w-24 text-end text-xs tnum shrink-0" style={{ color: 'var(--color-moca-sub)' }}>{a.pct}% · {fmtNum(a.n)}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Workspace rollup + event-type breakdown */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-moca-border">
            <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>פעילות לפי Workspace</h3>
          </div>
          {workspaceRollup.length === 0 ? (
            <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>אין נתונים</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[420px]">
                <thead style={{ background: 'var(--color-moca-mist)' }}>
                  <tr>
                    <th className="px-3 py-2 text-start text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>Workspace</th>
                    <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>משתמשים</th>
                    <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>פעילים</th>
                    <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>צפיות</th>
                    <th className="px-3 py-2 text-end text-xs font-semibold" style={{ color: 'var(--color-moca-muted)' }}>פעולות</th>
                  </tr>
                </thead>
                <tbody>
                  {workspaceRollup.map((w) => (
                    <tr key={w.name} className="border-t border-moca-border">
                      <td className="px-3 py-2 text-start" style={{ color: 'var(--color-moca-text)' }}>{w.name}</td>
                      <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-sub)' }}>{fmtNum(w.users)}</td>
                      <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(w.active)}</td>
                      <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(w.page_views)}</td>
                      <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(w.actions)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-moca-border">
            <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>פילוח לפי סוג אירוע</h3>
          </div>
          {(summary.by_event_type || []).length === 0 ? (
            <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>אין נתונים</p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {summary.by_event_type.map((e) => (
                  <tr key={e.event_type} className="border-t border-moca-border first:border-t-0">
                    <td className="px-4 py-2.5 text-start" style={{ color: 'var(--color-moca-text)' }}>
                      {EVENT_LABELS[e.event_type] || e.event_type}
                    </td>
                    <td className="px-4 py-2.5 text-end tnum font-semibold" style={{ color: 'var(--color-moca-dark)' }}>
                      {fmtNum(e.count)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Top pages */}
      <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-moca-border">
          <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>עמודים מובילים</h3>
        </div>
        {(summary.top_pages || []).length === 0 ? (
          <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>אין נתונים</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {summary.top_pages.map((p) => (
                <tr key={p.path} className="border-t border-moca-border first:border-t-0">
                  <td className="px-4 py-2.5 text-start" style={{ color: 'var(--color-moca-text)' }}>
                    {pageLabel(p.path)}
                  </td>
                  <td className="px-4 py-2.5 text-start text-xs" style={{ color: 'var(--color-moca-muted)' }}>
                    {p.path}
                  </td>
                  <td className="px-4 py-2.5 text-end tnum font-semibold" style={{ color: 'var(--color-moca-dark)' }}>
                    {fmtNum(p.views)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Per-user table */}
      <div className="rounded-xl border border-moca-border bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-moca-border">
          <h3 className="text-sm font-bold" style={{ color: 'var(--color-moca-dark)' }}>
            משתמשים ({fmtNum(users.length)})
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-moca-muted)' }}>
            לחיצה על שורה מציגה את פירוט הפעילות של המשתמש
          </p>
        </div>
        {users.length === 0 ? (
          <p className="text-sm p-4" style={{ color: 'var(--color-moca-muted)' }}>אין משתמשים להצגה</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[980px]">
              <thead style={{ background: 'var(--color-moca-mist)' }}>
                <tr>
                  <Th label="משתמש"        sortField="email"           sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="start" />
                  <Th label="תפקיד"        sortField="role"            sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="start" />
                  <Th label="Workspace"    sortField="workspace_name"  sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} align="start" />
                  <Th label="הצטרף"        sortField="created_at"      sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="התחברות אחרונה" sortField="last_sign_in_at" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="התחברויות"    sortField="logins"          sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="צפיות"        sortField="page_views"      sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="התראות"       sortField="alerts_created"  sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="מעקב"         sortField="watchlist_added" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="השוואות"      sortField="comparisons_saved" sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="צ׳אט"         sortField="chat_used"       sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                  <Th label="פעילות אחרונה" sortField="last_seen"       sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                </tr>
              </thead>
              <tbody>
                {sortedUsers.map((u) => (
                  <tr
                    key={u.id}
                    onClick={() => setOpenEmail(u.email)}
                    className="border-t border-moca-border cursor-pointer hover:bg-moca-mist"
                  >
                    <td className="px-3 py-2 text-start" style={{ color: 'var(--color-moca-text)' }}>{u.email}</td>
                    <td className="px-3 py-2 text-start"><RoleBadge role={u.role} /></td>
                    <td className="px-3 py-2 text-start text-xs" style={{ color: 'var(--color-moca-sub)' }}>{u.workspace_name || '—'}</td>
                    <td className="px-3 py-2 text-end text-xs tnum" style={{ color: 'var(--color-moca-sub)' }}>{fmtDate(u.created_at)}</td>
                    <td className="px-3 py-2 text-end text-xs tnum" style={{ color: 'var(--color-moca-text)' }}>{u.last_sign_in_at ? fmtDateTime(u.last_sign_in_at) : '—'}</td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(u.logins)}</td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(u.page_views)}</td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(u.alerts_created)}</td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(u.watchlist_added)}</td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(u.comparisons_saved)}</td>
                    <td className="px-3 py-2 text-end tnum" style={{ color: 'var(--color-moca-text)' }}>{fmtNum(u.chat_used)}</td>
                    <td className="px-3 py-2 text-end text-xs" style={{ color: 'var(--color-moca-sub)' }}>{fmtRelative(u.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Drill-down modal */}
      {openEmail && (
        <div
          className="fixed inset-0 z-[9000] flex items-center justify-center p-4"
          style={{ background: 'rgba(40,30,15,0.35)' }}
          onClick={() => setOpenEmail(null)}
        >
          <div
            className="bg-white rounded-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col"
            style={{ boxShadow: 'var(--sh-modal)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 py-4 border-b border-moca-border flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-moca-muted)' }}>
                  פעילות אחרונה
                </div>
                <div className="text-sm font-bold truncate" style={{ color: 'var(--color-moca-dark)' }}>{openEmail}</div>
              </div>
              <button
                onClick={() => setOpenEmail(null)}
                className="text-2xl leading-none px-2 shrink-0"
                style={{ color: 'var(--color-moca-sub)' }}
                aria-label="סגור"
              >
                ×
              </button>
            </div>
            <div className="overflow-y-auto">
              {eventsLoading ? (
                <p className="text-sm p-5" style={{ color: 'var(--color-moca-muted)' }}>טוען…</p>
              ) : events.length === 0 ? (
                <p className="text-sm p-5" style={{ color: 'var(--color-moca-muted)' }}>אין פעילות מתועדת בטווח הזה</p>
              ) : (
                <ul>
                  {events.map((ev) => {
                    const sub = ev.event_type === 'page_view' ? pageLabel(ev.path) : detailSummary(ev.details)
                    return (
                      <li key={ev.id} className="flex items-center justify-between gap-3 px-5 py-2.5 border-b border-moca-border last:border-b-0">
                        <div className="min-w-0">
                          <div className="text-sm font-medium" style={{ color: 'var(--color-moca-text)' }}>
                            {EVENT_LABELS[ev.event_type] || ev.event_type}
                          </div>
                          {sub && (
                            <div className="text-xs truncate" style={{ color: 'var(--color-moca-sub)' }}>{sub}</div>
                          )}
                        </div>
                        <div className="text-xs whitespace-nowrap tnum" style={{ color: 'var(--color-moca-muted)' }}>
                          {fmtDateTime(ev.created_at)}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
