import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Button from '../components/ui/Button'
import { api } from '../lib/api'
import { getMvnoColors, isKnownMvnoPrimary } from '../data/mvnoBrandColors'

const DOMESTIC_CARRIERS = [
  { id: 'partner',   label: 'פרטנר' },
  { id: 'pelephone', label: 'פלאפון' },
  { id: 'hotmobile', label: 'הוט מובייל' },
  { id: 'cellcom',   label: 'סלקום' },
  { id: 'mobile019', label: '019' },
  { id: 'xphone',    label: 'XPhone' },
  { id: 'wecom',     label: 'We-Com' },
  { id: 'neptucom',  label: 'Neptucom' },
]

// Switch MVNO in a form: auto-fill colors if the current primary is empty
// or matches a known MVNO default (i.e. not a user-chosen custom color).
function withMvnoColors(form, newMvno) {
  const nextColors = getMvnoColors(newMvno)
  const userHasCustomColor = form.primary_color && !isKnownMvnoPrimary(form.primary_color)
  if (userHasCustomColor) {
    return { ...form, mvno_carrier: newMvno }
  }
  return {
    ...form,
    mvno_carrier:    newMvno,
    primary_color:   nextColors?.primary   || '',
    secondary_color: nextColors?.secondary || '',
  }
}

const FLAG_DEFINITIONS = [
  { key: 'hide_abroad',            label: 'הסתר טאב חו"ל' },
  { key: 'hide_global',            label: 'הסתר טאב גלובלי' },
  { key: 'hide_content',           label: 'הסתר טאב תוכן' },
  { key: 'hide_banners',           label: 'הסתר טאב באנרים' },
  { key: 'hide_history',           label: 'הסתר טאב היסטוריה' },
  { key: 'hide_news',              label: 'הסתר טאב חדשות' },
  { key: 'hide_compare',           label: 'הסתר עמוד השוואה' },
  { key: 'hide_alerts',            label: 'הסתר עמוד התראות' },
  { key: 'hide_executive_summary', label: 'הסתר תקציר מנהלים' },
  { key: 'hide_archive',           label: 'הסתר ארכיב' },
  { key: 'hide_chat',              label: "הסתר צ'אט AI" },
]

const MVNO_OPTIONS = [
  { id: '',          label: '— ללא —' },
  { id: 'partner',   label: 'פרטנר' },
  { id: 'pelephone', label: 'פלאפון' },
  { id: 'hotmobile', label: 'הוט מובייל' },
  { id: 'cellcom',   label: 'סלקום' },
  { id: 'mobile019', label: '019' },
  { id: 'xphone',    label: 'XPhone' },
  { id: 'wecom',     label: 'We-Com' },
  { id: 'neptucom',  label: 'Neptucom' },
  { id: 'golan',     label: 'גולן טלקום' },
  { id: 'rami_levy', label: 'רמי לוי' },
]

function StatusPill({ active }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
      active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-200 text-gray-600'
    }`}>
      {active ? 'פעיל' : 'מושעה'}
    </span>
  )
}

function UsersSection({ workspaceId, onChange }) {
  const [users, setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [newEmail, setNewEmail] = useState('')
  const [newRole, setNewRole]   = useState('viewer')
  const [assigning, setAssigning] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      setUsers(await api.getWorkspaceUsers(workspaceId))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => { load() }, [load])

  const assign = async (e) => {
    e.preventDefault()
    if (!newEmail.trim()) return
    setAssigning(true); setError(null)
    try {
      await api.assignWorkspaceUser(workspaceId, newEmail.trim(), newRole)
      setNewEmail('')
      await load()
      onChange?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setAssigning(false)
    }
  }

  const unassign = async (userId) => {
    if (!confirm('להעביר את המשתמש ל-moca-internal?')) return
    setError(null)
    try {
      await api.unassignWorkspaceUser(workspaceId, userId)
      await load()
      onChange?.()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="bg-moca-cream/50 rounded-lg p-4 mt-3">
      <h4 className="text-sm font-semibold mb-2">משתמשים משויכים</h4>
      {loading ? (
        <p className="text-xs text-gray-500">טוען…</p>
      ) : users.length === 0 ? (
        <p className="text-xs text-gray-500">אין משתמשים ב-workspace זה.</p>
      ) : (
        <table className="w-full text-sm mb-3">
          <thead>
            <tr className="text-xs text-gray-500 border-b">
              <th className="text-right py-1">אימייל</th>
              <th className="text-right py-1">תפקיד</th>
              <th className="text-right py-1">כניסה אחרונה</th>
              <th className="text-right py-1"></th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b border-moca-border/30">
                <td className="py-1.5">{u.email}</td>
                <td className="py-1.5">{u.role}</td>
                <td className="py-1.5 text-xs text-gray-500">
                  {u.last_sign_in_at ? new Date(u.last_sign_in_at).toLocaleDateString('he-IL') : '—'}
                </td>
                <td className="py-1.5 text-left">
                  <button onClick={() => unassign(u.id)}
                    className="text-xs text-red-600 hover:underline">הסרה</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form onSubmit={assign} className="flex gap-2 items-center flex-wrap">
        <input type="email" required placeholder="email@example.com" value={newEmail}
          onChange={e => setNewEmail(e.target.value)}
          className="px-2 py-1 text-sm border border-moca-border rounded flex-1 min-w-[200px]" />
        <select value={newRole} onChange={e => setNewRole(e.target.value)}
          className="px-2 py-1 text-sm border border-moca-border rounded">
          <option value="viewer">viewer</option>
          <option value="admin">admin</option>
        </select>
        <Button type="submit" disabled={assigning} variant="primary" size="sm">
          {assigning ? '…' : 'שייך'}
        </Button>
      </form>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </div>
  )
}

function ColorInput({ label, value, onChange, defaultColor = null, defaultLabel = null }) {
  const usingDefault = !value && defaultColor
  return (
    <label className="text-sm">
      <span className="block mb-1 text-gray-700">{label}</span>
      <div className="flex items-center gap-2">
        <input type="color" value={value || defaultColor || '#5c3317'}
          onChange={e => onChange(e.target.value)}
          className="w-8 h-8 rounded cursor-pointer border border-moca-border p-0.5 bg-white" />
        <input type="text" value={value} onChange={e => onChange(e.target.value)}
          placeholder={defaultColor || '#e8003d'}
          className="flex-1 px-3 py-1.5 border border-moca-border rounded font-mono text-sm" />
        {value && (
          <button type="button" onClick={() => onChange('')}
            title="אפס לצבע ברירת-המחדל של הספק"
            className="text-xs text-gray-400 hover:text-red-500">✕</button>
        )}
      </div>
      {usingDefault && (
        <p className="text-[11px] text-gray-500 mt-1">
          משתמש בצבע של {defaultLabel || 'הספק'}: <code className="font-mono">{defaultColor}</code>
        </p>
      )}
    </label>
  )
}

function trialBadge(ws) {
  if (!ws.trial_ends_at) return null
  const end  = new Date(ws.trial_ends_at)
  const days = Math.ceil((end - Date.now()) / 86400000)
  if (ws.trial_expired || days < 0)
    return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">פיילוט פג</span>
  if (days <= 7)
    return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">{days}י׳ נותרו</span>
  return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">{days}י׳ נותרו</span>
}

function WorkspaceRow({ ws, onChange }) {
  const [expanded, setExpanded]   = useState(false)
  const [editing, setEditing]     = useState(false)
  const [form, setForm]           = useState({
    name:              ws.name,
    mvno_carrier:      ws.mvno_carrier || '',
    hide_self_carrier: ws.hide_self_carrier,
    active:            ws.active,
    primary_color:     ws.brand_config?.primary_color || '',
    secondary_color:   ws.brand_config?.secondary_color || '',
    app_title:         ws.brand_config?.app_title || '',
    logo_url:          ws.brand_config?.logo_url || '',
    feature_flags:     ws.feature_flags || {},
    trial_ends_at:     ws.trial_ends_at ? ws.trial_ends_at.slice(0, 10) : '',
    visible_carriers:  ws.visible_carriers || [],
  })
  const [saving, setSaving]       = useState(false)
  const [error, setError]         = useState(null)
  const [inviteOpen, setInviteOpen]   = useState(false)
  const [inviteRole, setInviteRole]   = useState('viewer')
  const [inviteLink, setInviteLink]   = useState(null)
  const [inviting, setInviting]       = useState(false)
  const [inviteErr, setInviteErr]     = useState(null)
  const [copied, setCopied]           = useState(false)
  const [digestSending, setDigestSending] = useState(false)
  const [digestResult, setDigestResult]   = useState(null)

  const sendDigest = async () => {
    setDigestSending(true); setDigestResult(null)
    try {
      const res = await api.triggerDigest(ws.id)
      setDigestResult({ ok: true, msg: `נשלח ל-${res.emails ?? 0} נמענים` })
    } catch (e) {
      setDigestResult({ ok: false, msg: e.message })
    } finally {
      setDigestSending(false)
    }
  }

  const generateInvite = async () => {
    setInviting(true); setInviteErr(null); setInviteLink(null); setCopied(false)
    try {
      const { token } = await api.createInvite(ws.id, inviteRole)
      setInviteLink(`${window.location.origin}/invite/${token}`)
    } catch (e) {
      setInviteErr(e.message)
    } finally {
      setInviting(false)
    }
  }

  const copyInviteLink = () => {
    navigator.clipboard.writeText(inviteLink).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  const save = async () => {
    setSaving(true); setError(null)
    try {
      await api.updateWorkspace(ws.id, {
        name:              form.name,
        mvno_carrier:      form.mvno_carrier || null,
        hide_self_carrier: form.hide_self_carrier,
        active:            form.active,
        trial_ends_at:     form.trial_ends_at || null,
        brand_config: {
          primary_color:   form.primary_color || null,
          secondary_color: form.secondary_color || null,
          app_title:       form.app_title || null,
          logo_url:        form.logo_url || null,
        },
        feature_flags:     form.feature_flags,
        visible_carriers:  form.visible_carriers,
      })
      setEditing(false)
      await onChange?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border border-moca-border/60 rounded-xl p-4 bg-white">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-xs bg-moca-cream px-2 py-0.5 rounded font-mono">{ws.slug}</code>
            {editing ? (
              <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                className="font-semibold text-lg border border-moca-border rounded px-2 py-0.5" />
            ) : (
              <span className="font-semibold text-lg">{ws.name}</span>
            )}
            <StatusPill active={ws.active} />
            {trialBadge(ws)}
          </div>
          <div className="flex gap-4 items-center text-sm text-gray-600 mt-2 flex-wrap">
            <span>
              MVNO:{' '}
              {editing ? (
                <select value={form.mvno_carrier}
                  onChange={e => setForm(withMvnoColors(form, e.target.value))}
                  className="border border-moca-border rounded px-1 py-0.5 text-sm">
                  {MVNO_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
                </select>
              ) : (
                <strong>{MVNO_OPTIONS.find(o => o.id === (ws.mvno_carrier || ''))?.label || ws.mvno_carrier || '—'}</strong>
              )}
            </span>
            <span>משתמשים: <strong>{ws.user_count}</strong></span>
            {ws.last_login && (
              <span>כניסה אחרונה: <strong>{new Date(ws.last_login).toLocaleDateString('he-IL')}</strong></span>
            )}
            {ws.refresh_limit != null && (
              <span className="flex items-center gap-1">
                רענונים:&nbsp;
                {Array.from({ length: ws.refresh_limit }).map((_, i) => (
                  <span key={i} className={`inline-block w-2.5 h-2.5 rounded-full ${
                    i < (ws.refresh_limit - (ws.refresh_count_month || 0)) ? 'bg-emerald-400' : 'bg-gray-200'
                  }`} />
                ))}
                <span className="text-xs text-gray-500 mr-1">
                  {ws.refresh_limit - (ws.refresh_count_month || 0)}/{ws.refresh_limit}
                </span>
              </span>
            )}
            {!editing && ws.visible_carriers?.length > 0 && (
              <span className="text-xs text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full px-2 py-0.5">
                {ws.visible_carriers.length} ספקים גלויים
              </span>
            )}
            <label className="flex items-center gap-1 cursor-pointer">
              <input type="checkbox" checked={editing ? form.hide_self_carrier : ws.hide_self_carrier}
                disabled={!editing}
                onChange={e => setForm({...form, hide_self_carrier: e.target.checked})} />
              <span className="text-xs">הסתר ספק עצמי</span>
            </label>
            <label className="flex items-center gap-1 cursor-pointer">
              <input type="checkbox" checked={editing ? form.active : ws.active}
                disabled={!editing}
                onChange={e => setForm({...form, active: e.target.checked})} />
              <span className="text-xs">פעיל</span>
            </label>
          </div>
        </div>
        <div className="flex gap-2">
          {editing ? (
            <>
              <Button onClick={save} disabled={saving} variant="primary" size="sm">
                {saving ? 'שומר…' : 'שמור'}
              </Button>
              <Button onClick={() => { setEditing(false); setForm({
                name: ws.name, mvno_carrier: ws.mvno_carrier || '',
                hide_self_carrier: ws.hide_self_carrier, active: ws.active,
                primary_color: ws.brand_config?.primary_color || '',
                secondary_color: ws.brand_config?.secondary_color || '',
                app_title: ws.brand_config?.app_title || '',
                logo_url: ws.brand_config?.logo_url || '',
                feature_flags:    ws.feature_flags || {},
                trial_ends_at:    ws.trial_ends_at ? ws.trial_ends_at.slice(0, 10) : '',
                visible_carriers: ws.visible_carriers || [],
              }) }} variant="ghost" size="sm">ביטול</Button>
            </>
          ) : (
            <>
              <Button onClick={() => setEditing(true)} variant="ghost" size="sm">עריכה</Button>
              <Button onClick={() => { setInviteOpen(o => !o); setInviteLink(null); setInviteErr(null) }} variant="ghost" size="sm">
                {inviteOpen ? 'סגור הזמנה' : 'הזמן משתמש'}
              </Button>
              <Button onClick={sendDigest} disabled={digestSending} variant="ghost" size="sm">
                {digestSending ? 'שולח…' : 'שלח דייג׳סט'}
              </Button>
              <Button onClick={() => setExpanded(e => !e)} variant="ghost" size="sm">
                {expanded ? 'סגור משתמשים' : 'ניהול משתמשים'}
              </Button>
            </>
          )}
        </div>
      </div>
      {digestResult && (
        <p className={`text-xs mt-2 px-3 py-1.5 rounded-lg ${
          digestResult.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'
        }`}>{digestResult.msg}</p>
      )}
      {inviteOpen && (
        <div className="bg-moca-cream/50 rounded-lg p-4 mt-3">
          <h4 className="text-sm font-semibold mb-3">הזמנת משתמש חדש</h4>
          <div className="flex gap-2 items-center flex-wrap">
            <select value={inviteRole} onChange={e => { setInviteRole(e.target.value); setInviteLink(null) }}
              className="px-2 py-1.5 text-sm border border-moca-border rounded">
              <option value="viewer">viewer — צופה</option>
              <option value="admin">admin — מנהל</option>
            </select>
            <Button onClick={generateInvite} disabled={inviting} variant="primary" size="sm">
              {inviting ? 'יוצר…' : 'צור קישור הזמנה'}
            </Button>
          </div>
          {inviteErr && <p className="text-xs text-red-600 mt-2">{inviteErr}</p>}
          {inviteLink && (
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <input readOnly value={inviteLink} dir="ltr"
                className="flex-1 min-w-0 px-2 py-1.5 text-xs border border-moca-border rounded bg-white font-mono" />
              <button onClick={copyInviteLink}
                className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                  copied
                    ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                    : 'bg-white border-moca-border text-moca-text hover:border-moca-bolt'
                }`}>
                {copied ? '✓ הועתק' : 'העתק'}
              </button>
            </div>
          )}
          {inviteLink && (
            <p className="text-xs text-gray-400 mt-1.5">תוקף 48 שעות · שימוש חד-פעמי</p>
          )}
        </div>
      )}
      {editing && (() => {
        const mvnoColors = getMvnoColors(form.mvno_carrier)
        const mvnoLabel  = MVNO_OPTIONS.find(o => o.id === form.mvno_carrier)?.label
        return (
        <div className="mt-3 pt-3 border-t border-moca-border/40 grid grid-cols-1 md:grid-cols-2 gap-3">
          <ColorInput label="צבע ראשי (primary)" value={form.primary_color}
            defaultColor={mvnoColors?.primary} defaultLabel={mvnoLabel}
            onChange={v => setForm({...form, primary_color: v})} />
          <ColorInput label="צבע משני (secondary)" value={form.secondary_color}
            defaultColor={mvnoColors?.secondary} defaultLabel={mvnoLabel}
            onChange={v => setForm({...form, secondary_color: v})} />
          <label className="text-sm">
            <span className="block mb-1 text-gray-700">כותרת האפליקציה</span>
            <input type="text" value={form.app_title}
              onChange={e => setForm({...form, app_title: e.target.value})}
              placeholder="Partner Intelligence"
              className="w-full px-3 py-1.5 border border-moca-border rounded" />
          </label>
          <label className="text-sm">
            <span className="block mb-1 text-gray-700">לוגו URL</span>
            <input type="url" value={form.logo_url}
              onChange={e => setForm({...form, logo_url: e.target.value})}
              placeholder="https://..."
              className="w-full px-3 py-1.5 border border-moca-border rounded" />
          </label>
          <label className="text-sm">
            <span className="block mb-1 text-gray-700">תאריך סיום פיילוט (trial_ends_at)</span>
            <input type="date" value={form.trial_ends_at}
              onChange={e => setForm({...form, trial_ends_at: e.target.value})}
              className="w-full px-3 py-1.5 border border-moca-border rounded" />
          </label>
          <div className="col-span-2 pt-2 border-t border-moca-border/30">
            <p className="text-sm font-medium text-gray-700 mb-2">ספקים גלויים (ריק = כולם)</p>
            <p className="text-xs text-gray-500 mb-2">אם נבחר לפחות ספק אחד — הworkspace יראה רק אותם.</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {DOMESTIC_CARRIERS.map(({ id, label }) => (
                <label key={id} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox"
                    checked={form.visible_carriers.includes(id)}
                    onChange={e => {
                      const next = e.target.checked
                        ? [...form.visible_carriers, id]
                        : form.visible_carriers.filter(c => c !== id)
                      setForm({ ...form, visible_carriers: next })
                    }} />
                  {label}
                </label>
              ))}
            </div>
          </div>
          <div className="col-span-2 pt-2 border-t border-moca-border/30">
            <p className="text-sm font-medium text-gray-700 mb-2">הסתרת תכנים (Feature Flags)</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {FLAG_DEFINITIONS.map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={!!form.feature_flags?.[key]}
                    onChange={e => setForm({ ...form, feature_flags: {
                      ...form.feature_flags, [key]: e.target.checked || undefined
                    }})} />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>
        )
      })()}
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
      {expanded && <UsersSection workspaceId={ws.id} onChange={onChange} />}
    </div>
  )
}

function StatsBar({ list, recentEvents }) {
  const totalUsers   = list.reduce((s, w) => s + (w.user_count || 0), 0)
  const activeCount  = list.filter(w => w.active).length
  const expiringSoon = list.filter(w => {
    if (!w.trial_ends_at || w.trial_expired) return false
    return Math.ceil((new Date(w.trial_ends_at) - Date.now()) / 86400000) <= 7
  }).length

  const stats = [
    { label: 'Workspaces', value: list.length, color: 'text-moca-text' },
    { label: 'פעילים', value: activeCount, color: 'text-emerald-600' },
    { label: 'משתמשים', value: totalUsers, color: 'text-blue-600' },
    { label: 'פיילוט פג בקרוב', value: expiringSoon, color: expiringSoon > 0 ? 'text-amber-600' : 'text-gray-400' },
  ]

  return (
    <div className="mb-6 space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map(s => (
          <div key={s.label} className="bg-white border border-moca-border/60 rounded-xl p-4 text-center">
            <div className={`text-3xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs text-gray-500 mt-1">{s.label}</div>
          </div>
        ))}
      </div>
      {recentEvents.length > 0 && (
        <div className="bg-white border border-moca-border/60 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-gray-700">פעילות אחרונה</p>
            <Link to="/admin/audit" className="text-xs text-moca-bolt hover:underline">כל הרשומות ←</Link>
          </div>
          <div className="space-y-1.5">
            {recentEvents.map(e => (
              <div key={e.id} className="flex items-center gap-3 text-xs text-gray-600">
                <span className="text-gray-400 whitespace-nowrap">
                  {e.created_at ? new Date(e.created_at).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                </span>
                <span className="font-medium">{e.action}</span>
                <span className="truncate text-gray-400">{e.actor_email || ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function WorkspacesAdminPage() {
  const [list, setList]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [creating, setCreating] = useState(false)
  const [recentEvents, setRecentEvents] = useState([])
  const [form, setForm]         = useState({
    slug: '', name: '', mvno_carrier: '', hide_self_carrier: true,
    primary_color: '', secondary_color: '', app_title: '', logo_url: '',
    feature_flags: {},
  })
  const [createError, setCreateError] = useState(null)
  const [submitting, setSubmitting]   = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [workspaces, audit] = await Promise.all([
        api.getWorkspaces(),
        api.getAuditLog('?limit=5'),
      ])
      setList(workspaces)
      setRecentEvents(audit)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const create = async (e) => {
    e.preventDefault()
    setSubmitting(true); setCreateError(null)
    try {
      await api.createWorkspace({
        slug: form.slug.trim().toLowerCase(),
        name: form.name.trim(),
        mvno_carrier: form.mvno_carrier || null,
        hide_self_carrier: form.hide_self_carrier,
        brand_config: {
          primary_color:   form.primary_color || null,
          secondary_color: form.secondary_color || null,
          app_title:       form.app_title || null,
          logo_url:        form.logo_url || null,
        },
        feature_flags: form.feature_flags,
      })
      setForm({ slug: '', name: '', mvno_carrier: '', hide_self_carrier: true,
        primary_color: '', secondary_color: '', app_title: '', logo_url: '', feature_flags: {} })
      setCreating(false)
      await load()
    } catch (e) {
      setCreateError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">ניהול Workspaces</h1>
          <p className="text-sm text-gray-600 mt-1">
            כל workspace הוא לקוח MVNO נפרד עם צבעי מותג, feature flags וסינון ספקים משלו.
          </p>
        </div>
        <Button onClick={() => setCreating(c => !c)} variant="primary">
          {creating ? 'סגור' : '+ workspace חדש'}
        </Button>
      </div>

      {!loading && !error && <StatsBar list={list} recentEvents={recentEvents} />}

      {creating && (
        <form onSubmit={create}
          className="bg-moca-cream border border-moca-border rounded-xl p-5 mb-6 space-y-3">
          <h3 className="font-semibold">יצירת workspace</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">Slug (מזהה URL) *</span>
              <input required pattern="[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?"
                value={form.slug}
                onChange={e => setForm({...form, slug: e.target.value.toLowerCase()})}
                placeholder="partner-pilot"
                className="w-full px-3 py-1.5 border border-moca-border rounded" />
            </label>
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">שם תצוגה *</span>
              <input required value={form.name}
                onChange={e => setForm({...form, name: e.target.value})}
                placeholder="Partner Intelligence"
                className="w-full px-3 py-1.5 border border-moca-border rounded" />
            </label>
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">MVNO של הלקוח</span>
              <select value={form.mvno_carrier}
                onChange={e => setForm(withMvnoColors(form, e.target.value))}
                className="w-full px-3 py-1.5 border border-moca-border rounded">
                {MVNO_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </label>
            <label className="text-sm flex items-end gap-2 cursor-pointer">
              <input type="checkbox" checked={form.hide_self_carrier}
                onChange={e => setForm({...form, hide_self_carrier: e.target.checked})} />
              <span>הסתר ספק עצמי מהתוצאות</span>
            </label>
            <ColorInput label="צבע ראשי (primary)" value={form.primary_color}
              defaultColor={getMvnoColors(form.mvno_carrier)?.primary}
              defaultLabel={MVNO_OPTIONS.find(o => o.id === form.mvno_carrier)?.label}
              onChange={v => setForm({...form, primary_color: v})} />
            <ColorInput label="צבע משני (secondary)" value={form.secondary_color}
              defaultColor={getMvnoColors(form.mvno_carrier)?.secondary}
              defaultLabel={MVNO_OPTIONS.find(o => o.id === form.mvno_carrier)?.label}
              onChange={v => setForm({...form, secondary_color: v})} />
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">כותרת האפליקציה</span>
              <input type="text" value={form.app_title}
                onChange={e => setForm({...form, app_title: e.target.value})}
                placeholder="Partner Intelligence"
                className="w-full px-3 py-1.5 border border-moca-border rounded" />
            </label>
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">לוגו URL</span>
              <input type="url" value={form.logo_url}
                onChange={e => setForm({...form, logo_url: e.target.value})}
                placeholder="https://..."
                className="w-full px-3 py-1.5 border border-moca-border rounded" />
            </label>
          </div>
          {createError && <p className="text-sm text-red-600">{createError}</p>}
          <div className="flex gap-2">
            <Button type="submit" disabled={submitting} variant="primary">
              {submitting ? 'יוצר…' : 'צור'}
            </Button>
            <Button type="button" onClick={() => setCreating(false)} variant="ghost">ביטול</Button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">טוען…</p>
      ) : error ? (
        <p className="text-red-600">שגיאה: {error}</p>
      ) : (
        <div className="space-y-3">
          {list.map(ws => <WorkspaceRow key={ws.id} ws={ws} onChange={load} />)}
        </div>
      )}
    </div>
  )
}
