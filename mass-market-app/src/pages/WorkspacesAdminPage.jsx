import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Button from '../components/ui/Button'
import SearchableSelect from '../components/ui/SearchableSelect'
import LogoField from '../components/LogoField'
import { api } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'
import { getMvnoColors, isKnownMvnoPrimary } from '../data/mvnoBrandColors'
import { DISPLAY_PRESETS, applyDisplayPreset, detectDisplayPreset } from '../data/navFlags'

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

// Keep these keys in sync with FLAG_FOR_PATH (src/data/navFlags.js) — every key
// here must be consulted by a nav item / page, otherwise the checkbox hides
// nothing. `hide_chat` is consulted separately in Layout.jsx (not a nav item).
const FLAG_DEFINITIONS = [
  { key: 'hide_dashboard',         label: 'הסתר דשבורד ראשי',    en: 'Hide main dashboard' },
  // מסלולים (tabs)
  { key: 'hide_domestic',          label: 'הסתר טאב סלולר',       en: 'Hide domestic tab' },
  { key: 'hide_abroad',            label: 'הסתר טאב חו"ל',        en: 'Hide roaming tab' },
  { key: 'hide_global',            label: 'הסתר טאב גלובלי',      en: 'Hide global tab' },
  { key: 'hide_global_banners',    label: 'הסתר באנרים גלובליים', en: 'Hide global banners' },
  { key: 'hide_usa',               label: 'הסתר טאב ארה"ב',       en: 'Hide USA tab' },
  { key: 'hide_resellers',         label: 'הסתר טאב משווקים',     en: 'Hide resellers tab' },
  { key: 'hide_content',           label: 'הסתר טאב תוכן',        en: 'Hide content tab' },
  { key: 'hide_banners',           label: 'הסתר טאב באנרים',      en: 'Hide banners tab' },
  { key: 'hide_history',           label: 'הסתר טאב היסטוריה',    en: 'Hide history tab' },
  { key: 'hide_news',              label: 'הסתר טאב חדשות',       en: 'Hide news tab' },
  { key: 'hide_social',            label: 'הסתר רשתות חברתיות',   en: 'Hide social media' },
  // עמודים / תובנות
  { key: 'hide_compare',           label: 'הסתר עמוד השוואה',     en: 'Hide compare page' },
  { key: 'hide_positioning',       label: 'הסתר מיצוב תחרותי',    en: 'Hide competitive positioning' },
  { key: 'hide_alerts',            label: 'הסתר עמוד התראות',     en: 'Hide alerts page' },
  { key: 'hide_executive_summary', label: 'הסתר תקציר מנהלים',    en: 'Hide executive summary' },
  { key: 'hide_ai_insights',       label: 'הסתר AI Insights',     en: 'Hide AI Insights' },
  { key: 'hide_archive',           label: 'הסתר מכונת זמן',       en: 'Hide Time Machine' },
  { key: 'hide_chat',              label: "הסתר צ'אט AI",         en: 'Hide AI chat' },
]

const MVNO_OPTIONS = [
  { id: '',          label: '- ללא -', en: '- None -' },
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
  const { tt } = useLang()
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
      active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-200 text-gray-600'
    }`}>
      {active ? tt('פעיל', 'Active') : tt('מושעה', 'Suspended')}
    </span>
  )
}

function UsersSection({ workspaceId, onChange }) {
  const { tt } = useLang()
  const [users, setUsers]   = useState([])
  const [allUsers, setAllUsers] = useState([])
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

  // All existing Supabase users — feeds the assignment dropdown so the
  // super-admin can pick a user instead of typing an email (avoids typos /
  // 404s, since assignment only works for users that already exist).
  useEffect(() => {
    let alive = true
    api.getUsers()
      .then(list => { if (alive) setAllUsers(Array.isArray(list) ? list : []) })
      .catch(() => {})
    return () => { alive = false }
  }, [])

  // Already-assigned users are marked (and sorted last) but kept selectable so
  // re-assigning can change an existing member's role.
  const userOptions = useMemo(() => {
    const assignedIds = new Set(users.map(u => u.id))
    return allUsers
      .map(u => ({
        value: u.email,
        label: assignedIds.has(u.id) ? `${u.email} · ${tt('כבר משויך', 'already assigned')}` : u.email,
        assigned: assignedIds.has(u.id),
      }))
      .sort((a, b) => (a.assigned - b.assigned) || a.value.localeCompare(b.value))
  }, [allUsers, users, tt])

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
    if (!confirm(tt('להעביר את המשתמש ל-moca-internal?', 'Move the user to moca-internal?'))) return
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
      <h4 className="text-sm font-semibold mb-2">{tt('משתמשים משויכים', 'Assigned users')}</h4>
      {loading ? (
        <p className="text-xs text-gray-500">{tt('טוען…', 'Loading…')}</p>
      ) : users.length === 0 ? (
        <p className="text-xs text-gray-500">{tt('אין משתמשים ב-workspace זה.', 'No users in this workspace.')}</p>
      ) : (
        <div className="overflow-x-auto mb-3">
          <table className="w-full text-sm min-w-[460px] md:min-w-0">
            <thead>
              <tr className="text-xs text-gray-500 border-b">
                <th className="text-right py-1 whitespace-nowrap">{tt('אימייל', 'Email')}</th>
                <th className="text-right py-1 whitespace-nowrap">{tt('תפקיד', 'Role')}</th>
                <th className="text-right py-1 whitespace-nowrap">{tt('כניסה אחרונה', 'Last login')}</th>
                <th className="text-right py-1"></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b border-moca-border/30">
                  <td className="py-1.5 whitespace-nowrap" dir="ltr">{u.email}</td>
                  <td className="py-1.5">{u.role}</td>
                  <td className="py-1.5 text-xs text-gray-500 whitespace-nowrap">
                    {u.last_sign_in_at ? new Date(u.last_sign_in_at).toLocaleDateString('he-IL') : '-'}
                  </td>
                  <td className="py-1.5 text-left">
                    <button onClick={() => unassign(u.id)}
                      className="text-xs text-red-600 hover:underline">{tt('הסרה', 'Remove')}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={assign} className="flex gap-2 items-center flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <SearchableSelect
            value={newEmail || 'all'}
            onChange={v => setNewEmail(v === 'all' ? '' : v)}
            options={userOptions}
            placeholder={tt('בחר משתמש לשיוך…', 'Select a user to assign…')}
            size="md"
          />
        </div>
        <select value={newRole} onChange={e => setNewRole(e.target.value)}
          className="px-2 py-1.5 text-sm border border-moca-border rounded">
          <option value="viewer">viewer</option>
          <option value="admin">admin</option>
        </select>
        <Button type="submit" disabled={assigning || !newEmail} variant="primary" size="sm">
          {assigning ? '…' : tt('שייך', 'Assign')}
        </Button>
      </form>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </div>
  )
}

function ColorInput({ label, value, onChange, defaultColor = null, defaultLabel = null }) {
  const { tt } = useLang()
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
            title={tt('אפס לצבע ברירת-המחדל של הספק', 'Reset to the carrier default color')}
            className="text-xs text-gray-400 hover:text-red-500">✕</button>
        )}
      </div>
      {usingDefault && (
        <p className="text-[11px] text-gray-500 mt-1">
          {tt('משתמש בצבע של', 'Using the color of')} {defaultLabel || tt('הספק', 'the carrier')}: <code className="font-mono">{defaultColor}</code>
        </p>
      )}
    </label>
  )
}

function trialBadge(ws, tt = (he) => he) {
  if (!ws.trial_ends_at) return null
  const end  = new Date(ws.trial_ends_at)
  const days = Math.ceil((end - Date.now()) / 86400000)
  if (ws.trial_expired || days < 0)
    return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">{tt('פיילוט פג', 'Trial expired')}</span>
  if (days <= 7)
    return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">{tt(`${days}י׳ נותרו`, `${days}d left`)}</span>
  return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">{tt(`${days}י׳ נותרו`, `${days}d left`)}</span>
}

function WorkspaceRow({ ws, onChange }) {
  const { enterViewAs } = useAuth()
  const { tt } = useLang()
  const navigate = useNavigate()
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
    slack_webhook_url: ws.brand_config?.slack_webhook_url || '',
    feature_flags:     ws.feature_flags || {},
    trial_ends_at:     ws.trial_ends_at ? ws.trial_ends_at.slice(0, 10) : '',
    visible_carriers:  ws.visible_carriers || [],
    digest_frequency:  ws.digest_frequency || 'weekly',
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
  const [bulkMode, setBulkMode]           = useState(false)
  const [bulkEmails, setBulkEmails]       = useState('')
  const [bulkResults, setBulkResults]     = useState(null)
  const [bulkCopiedAll, setBulkCopiedAll] = useState(false)

  const sendDigest = async () => {
    setDigestSending(true); setDigestResult(null)
    try {
      const res = await api.triggerDigest(ws.id)
      if (res.status === 'skipped') {
        setDigestResult({ ok: true, msg: tt(`לא נשלח - ${res.reason || 'אין שינויים'}`, `Not sent - ${res.reason || 'no changes'}`) })
      } else {
        setDigestResult({ ok: true, msg: tt(`נשלח ל-${res.emails ?? 0} נמענים · ${res.changes ?? 0} שינויים`, `Sent to ${res.emails ?? 0} recipients · ${res.changes ?? 0} changes`) })
      }
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

  const generateBulk = async () => {
    const emails = bulkEmails.split(/[\s,;\n]+/).map(s => s.trim()).filter(Boolean)
    if (emails.length === 0) { setInviteErr(tt('הדבק לפחות אימייל אחד', 'Paste at least one email')); return }
    setInviting(true); setInviteErr(null); setBulkResults(null); setBulkCopiedAll(false)
    try {
      const res = await api.createInviteBulk(ws.id, emails, inviteRole)
      setBulkResults(res.results || [])
    } catch (e) {
      setInviteErr(e.message)
    } finally {
      setInviting(false)
    }
  }

  const copyAllBulk = () => {
    if (!bulkResults) return
    const rows = bulkResults
      .filter(r => r.token)
      .map(r => `${r.email}\t${window.location.origin}/invite/${r.token}`)
      .join('\n')
    navigator.clipboard.writeText(rows).then(() => {
      setBulkCopiedAll(true)
      setTimeout(() => setBulkCopiedAll(false), 2500)
    })
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
          primary_color:     form.primary_color || null,
          secondary_color:   form.secondary_color || null,
          app_title:         form.app_title || null,
          logo_url:          form.logo_url || null,
          slack_webhook_url: form.slack_webhook_url || null,
        },
        feature_flags:     form.feature_flags,
        visible_carriers:  form.visible_carriers,
        digest_frequency:  form.digest_frequency,
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
            {trialBadge(ws, tt)}
          </div>
          <div className="flex gap-4 items-center text-sm text-gray-600 mt-2 flex-wrap">
            <span>
              MVNO:{' '}
              {editing ? (
                <select value={form.mvno_carrier}
                  onChange={e => setForm(withMvnoColors(form, e.target.value))}
                  className="border border-moca-border rounded px-1 py-0.5 text-sm">
                  {MVNO_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.en ? tt(o.label, o.en) : o.label}</option>)}
                </select>
              ) : (
                <strong>{(() => { const o = MVNO_OPTIONS.find(o => o.id === (ws.mvno_carrier || '')); return o ? (o.en ? tt(o.label, o.en) : o.label) : (ws.mvno_carrier || '-') })()}</strong>
              )}
            </span>
            <span>{tt('משתמשים:', 'Users:')} <strong>{ws.user_count}</strong></span>
            {ws.last_login && (
              <span>{tt('כניסה אחרונה:', 'Last login:')} <strong>{new Date(ws.last_login).toLocaleDateString('he-IL')}</strong></span>
            )}
            {ws.refresh_limit != null && (
              <span className="flex items-center gap-1">
                {tt('רענונים:', 'Refreshes:')}&nbsp;
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
                {ws.visible_carriers.length} {tt('ספקים גלויים', 'visible carriers')}
              </span>
            )}
            <label className="flex items-center gap-1 cursor-pointer">
              <input type="checkbox" checked={editing ? form.hide_self_carrier : ws.hide_self_carrier}
                disabled={!editing}
                onChange={e => setForm({...form, hide_self_carrier: e.target.checked})} />
              <span className="text-xs">{tt('הסתר ספק עצמי', 'Hide self carrier')}</span>
            </label>
            <label className="flex items-center gap-1 cursor-pointer">
              <input type="checkbox" checked={editing ? form.active : ws.active}
                disabled={!editing}
                onChange={e => setForm({...form, active: e.target.checked})} />
              <span className="text-xs">{tt('פעיל', 'Active')}</span>
            </label>
          </div>
        </div>
        <div className="flex gap-2">
          {editing ? (
            <>
              <Button onClick={save} disabled={saving} variant="primary" size="sm">
                {saving ? tt('שומר…', 'Saving…') : tt('שמור', 'Save')}
              </Button>
              <Button onClick={() => { setEditing(false); setForm({
                name: ws.name, mvno_carrier: ws.mvno_carrier || '',
                hide_self_carrier: ws.hide_self_carrier, active: ws.active,
                primary_color: ws.brand_config?.primary_color || '',
                secondary_color: ws.brand_config?.secondary_color || '',
                app_title: ws.brand_config?.app_title || '',
                logo_url: ws.brand_config?.logo_url || '',
                slack_webhook_url: ws.brand_config?.slack_webhook_url || '',
                feature_flags:    ws.feature_flags || {},
                trial_ends_at:    ws.trial_ends_at ? ws.trial_ends_at.slice(0, 10) : '',
                visible_carriers: ws.visible_carriers || [],
                digest_frequency: ws.digest_frequency || 'weekly',
              }) }} variant="ghost" size="sm">{tt('ביטול', 'Cancel')}</Button>
            </>
          ) : (
            <>
              <Button onClick={() => setEditing(true)} variant="ghost" size="sm" className="border border-moca-border/60">{tt('עריכה', 'Edit')}</Button>
              <Button
                onClick={() => {
                  enterViewAs({
                    id: ws.id, slug: ws.slug, name: ws.name,
                    mvno_carrier: ws.mvno_carrier,
                    brand_config: ws.brand_config || {},
                    feature_flags: ws.feature_flags || {},
                    hide_self_carrier: ws.hide_self_carrier,
                    visible_carriers: ws.visible_carriers || [],
                    active: true,
                  })
                  navigate('/')
                }}
                variant="ghost"
                size="sm"
                className="border border-moca-border/60"
                title={tt('צפה באפליקציה כפי שמשתמש של ה-workspace רואה אותה', 'View the app as a user of this workspace sees it')}
              >
                {tt('צפה כ', 'View as')}
              </Button>
              <Button onClick={() => { setInviteOpen(o => !o); setInviteLink(null); setInviteErr(null) }} variant="ghost" size="sm" className="border border-moca-border/60">
                {inviteOpen ? tt('סגור הזמנה', 'Close invite') : tt('הזמן משתמש', 'Invite user')}
              </Button>
              <Button onClick={sendDigest} disabled={digestSending} variant="ghost" size="sm" className="border border-moca-border/60">
                {digestSending ? tt('שולח…', 'Sending…') : tt('שלח דייג׳סט', 'Send digest')}
              </Button>
              <Button onClick={() => setExpanded(e => !e)} variant="ghost" size="sm" className="border border-moca-border/60">
                {expanded ? tt('סגור משתמשים', 'Close users') : tt('ניהול משתמשים', 'Manage users')}
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
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold">{tt('הזמנת משתמש חדש', 'Invite a new user')}</h4>
            <div className="flex bg-white rounded-lg border border-moca-border overflow-hidden text-xs">
              <button
                onClick={() => { setBulkMode(false); setBulkResults(null); setInviteErr(null) }}
                className={`px-3 py-1 transition-colors ${!bulkMode ? 'bg-moca-bolt text-white' : 'text-gray-600 hover:bg-moca-cream'}`}
              >{tt('יחיד', 'Single')}</button>
              <button
                onClick={() => { setBulkMode(true); setInviteLink(null); setInviteErr(null) }}
                className={`px-3 py-1 transition-colors ${bulkMode ? 'bg-moca-bolt text-white' : 'text-gray-600 hover:bg-moca-cream'}`}
              >Bulk</button>
            </div>
          </div>

          <div className="flex gap-2 items-center flex-wrap mb-2">
            <select value={inviteRole} onChange={e => { setInviteRole(e.target.value); setInviteLink(null); setBulkResults(null) }}
              className="px-2 py-1.5 text-sm border border-moca-border rounded">
              <option value="viewer">{tt('viewer - צופה', 'viewer')}</option>
              <option value="admin">{tt('admin - מנהל', 'admin')}</option>
            </select>
            {!bulkMode ? (
              <Button onClick={generateInvite} disabled={inviting} variant="primary" size="sm">
                {inviting ? tt('יוצר…', 'Creating…') : tt('צור קישור הזמנה', 'Create invite link')}
              </Button>
            ) : (
              <Button onClick={generateBulk} disabled={inviting} variant="primary" size="sm">
                {inviting ? tt('יוצר…', 'Creating…') : tt('צור הזמנות להמונים', 'Create bulk invites')}
              </Button>
            )}
          </div>

          {bulkMode && !bulkResults && (
            <>
              <textarea
                value={bulkEmails}
                onChange={e => setBulkEmails(e.target.value)}
                placeholder={tt("הדבק מיילים - אחד בכל שורה, מופרדים בפסיק או ברווח\nname1@partner.co.il\nname2@partner.co.il", "Paste emails - one per line, or comma/space separated\nname1@partner.co.il\nname2@partner.co.il")}
                rows={5}
                dir="ltr"
                className="w-full px-2 py-1.5 text-xs border border-moca-border rounded bg-white font-mono"
              />
              <p className="text-[11px] text-gray-400 mt-1">{tt('מקסימום 50 מיילים · לינק ייחודי לכל אחד · לא נשלח מייל אוטומטי', 'Max 50 emails · a unique link per recipient · no email is sent automatically')}</p>
            </>
          )}

          {inviteErr && <p className="text-xs text-red-600 mt-2">{inviteErr}</p>}

          {inviteLink && !bulkMode && (
            <>
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <input readOnly value={inviteLink} dir="ltr"
                  className="flex-1 min-w-0 px-2 py-1.5 text-xs border border-moca-border rounded bg-white font-mono" />
                <button onClick={copyInviteLink}
                  className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                    copied
                      ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                      : 'bg-white border-moca-border text-moca-text hover:border-moca-bolt'
                  }`}>
                  {copied ? tt('✓ הועתק', '✓ Copied') : tt('העתק', 'Copy')}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1.5">{tt('תוקף 7 ימים · שימוש חד-פעמי', 'Valid for 7 days · single use')}</p>
            </>
          )}

          {bulkResults && bulkMode && (
            <div className="mt-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-gray-600">
                  {tt('נוצרו', 'Created')} <strong>{bulkResults.filter(r => r.token).length}</strong> {tt(`הזמנות מתוך ${bulkResults.length}`, `invites of ${bulkResults.length}`)}
                </p>
                <div className="flex gap-2">
                  <button onClick={copyAllBulk}
                    className={`text-[11px] px-2 py-1 rounded border transition-colors ${
                      bulkCopiedAll
                        ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                        : 'bg-white border-moca-border text-moca-text hover:border-moca-bolt'
                    }`}>
                    {bulkCopiedAll ? tt('✓ הכל הועתק', '✓ All copied') : tt('העתק הכל (TSV)', 'Copy all (TSV)')}
                  </button>
                  <button onClick={() => { setBulkResults(null); setBulkEmails('') }}
                    className="text-[11px] text-gray-400 hover:text-moca-bolt px-1">
                    {tt('חדש', 'New')}
                  </button>
                </div>
              </div>
              <div className="max-h-56 overflow-y-auto bg-white rounded border border-moca-border">
                <table className="w-full text-xs">
                  <tbody>
                    {bulkResults.map((r, i) => (
                      <tr key={i} className="border-b border-moca-border/30 last:border-0">
                        <td className="py-1.5 px-2 text-gray-700 truncate max-w-[180px]" dir="ltr">{r.email}</td>
                        <td className="py-1.5 px-2" dir="ltr">
                          {r.token ? (
                            <input readOnly value={`${window.location.origin}/invite/${r.token}`}
                              className="w-full px-1.5 py-0.5 text-[11px] border border-moca-border/40 rounded bg-gray-50 font-mono"
                              onClick={e => e.target.select()} />
                          ) : (
                            <span className="text-red-500 text-[11px]">{r.error || tt('שגיאה', 'Error')}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
      {editing && (() => {
        const mvnoColors = getMvnoColors(form.mvno_carrier)
        const mvnoLabel  = MVNO_OPTIONS.find(o => o.id === form.mvno_carrier)?.label
        return (
        <div className="mt-3 pt-3 border-t border-moca-border/40 grid grid-cols-1 md:grid-cols-2 gap-3">
          <ColorInput label={tt('צבע ראשי (primary)', 'Primary color')} value={form.primary_color}
            defaultColor={mvnoColors?.primary} defaultLabel={mvnoLabel}
            onChange={v => setForm({...form, primary_color: v})} />
          <ColorInput label={tt('צבע משני (secondary)', 'Secondary color')} value={form.secondary_color}
            defaultColor={mvnoColors?.secondary} defaultLabel={mvnoLabel}
            onChange={v => setForm({...form, secondary_color: v})} />
          <label className="text-sm">
            <span className="block mb-1 text-gray-700">{tt('כותרת האפליקציה', 'App title')}</span>
            <input type="text" value={form.app_title}
              onChange={e => setForm({...form, app_title: e.target.value})}
              placeholder="Partner Intelligence"
              className="w-full px-3 py-1.5 border border-moca-border rounded" />
          </label>
          <div className="text-sm">
            <span className="block mb-1 text-gray-700">{tt('לוגו', 'Logo')}</span>
            <LogoField value={form.logo_url}
              onChange={v => setForm({...form, logo_url: v})} />
          </div>
          <label className="text-sm col-span-2">
            <span className="block mb-1 text-gray-700">Slack / Teams Webhook URL</span>
            <input type="url" value={form.slack_webhook_url}
              onChange={e => setForm({...form, slack_webhook_url: e.target.value})}
              placeholder="https://hooks.slack.com/services/..."
              dir="ltr"
              className="w-full px-3 py-1.5 border border-moca-border rounded font-mono text-xs" />
            <span className="block text-[10px] text-gray-400 mt-1">
              {tt('התראות אוטומטיות על שינויים בחבילות יישלחו לערוץ זה (לאחר סינון הספק העצמי).', 'Automatic alerts on plan changes are sent to this channel (after filtering the self carrier).')}
            </span>
          </label>
          <label className="text-sm">
            <span className="block mb-1 text-gray-700">{tt('תאריך סיום פיילוט (trial_ends_at)', 'Trial end date (trial_ends_at)')}</span>
            <input type="date" value={form.trial_ends_at}
              onChange={e => setForm({...form, trial_ends_at: e.target.value})}
              className="w-full px-3 py-1.5 border border-moca-border rounded" />
          </label>
          <label className="text-sm">
            <span className="block mb-1 text-gray-700">{tt('תדירות דייג\'סט דוא"ל', 'Email digest frequency')}</span>
            <select value={form.digest_frequency}
              onChange={e => setForm({...form, digest_frequency: e.target.value})}
              className="w-full px-3 py-1.5 border border-moca-border rounded bg-white">
              <option value="weekly">{tt('שבועי', 'Weekly')}</option>
              <option value="monthly">{tt('חודשי (ראשון בחודש)', 'Monthly (1st of month)')}</option>
              <option value="off">{tt('כבוי', 'Off')}</option>
            </select>
          </label>
          <div className="col-span-2 pt-2 border-t border-moca-border/30">
            <p className="text-sm font-medium text-gray-700 mb-2">{tt('ספקים גלויים (ריק = כולם)', 'Visible carriers (empty = all)')}</p>
            <p className="text-xs text-gray-500 mb-2">{tt('אם נבחר לפחות ספק אחד - הworkspace יראה רק אותם.', 'If at least one carrier is selected, the workspace will see only those.')}</p>
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
            <div className="flex items-center justify-between gap-3 flex-wrap mb-1">
              <p className="text-sm font-medium text-gray-700">{tt('הסתרת תכנים (Feature Flags)', 'Hide content (Feature Flags)')}</p>
              <label className="flex items-center gap-2 text-sm">
                <span className="text-gray-600 whitespace-nowrap">{tt('מצב תצוגה:', 'Display mode:')}</span>
                <select
                  className="border border-moca-border rounded-md px-2 py-1 text-sm bg-white cursor-pointer"
                  value={detectDisplayPreset(form.feature_flags)}
                  onChange={e => {
                    const id = e.target.value
                    if (id === 'custom') return
                    setForm({ ...form, feature_flags: applyDisplayPreset(form.feature_flags, id) })
                  }}
                >
                  {detectDisplayPreset(form.feature_flags) === 'custom' && (
                    <option value="custom">{tt('מותאם אישית', 'Custom')}</option>
                  )}
                  {DISPLAY_PRESETS.map(p => (
                    <option key={p.id} value={p.id}>{p.label}</option>
                  ))}
                </select>
              </label>
            </div>
            <p className="text-xs text-gray-500 mb-2">{tt('בחירת מצב תצוגה מסמנת את התיבות אוטומטית. אפשר גם לכוונן ידנית - זה יעבור ל"מותאם אישית".', 'Selecting a display mode ticks the boxes automatically. You can also fine-tune manually - it switches to "Custom".')}</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {FLAG_DEFINITIONS.map(({ key, label, en }) => (
                <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={!!form.feature_flags?.[key]}
                    onChange={e => setForm({ ...form, feature_flags: {
                      ...form.feature_flags, [key]: e.target.checked || undefined
                    }})} />
                  {tt(label, en)}
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
  const { tt } = useLang()
  const totalUsers   = list.reduce((s, w) => s + (w.user_count || 0), 0)
  const activeCount  = list.filter(w => w.active).length
  const expiringSoon = list.filter(w => {
    if (!w.trial_ends_at || w.trial_expired) return false
    return Math.ceil((new Date(w.trial_ends_at) - Date.now()) / 86400000) <= 7
  }).length

  const stats = [
    { label: 'Workspaces', value: list.length, color: 'text-moca-text' },
    { label: tt('פעילים', 'Active'), value: activeCount, color: 'text-emerald-600' },
    { label: tt('משתמשים', 'Users'), value: totalUsers, color: 'text-blue-600' },
    { label: tt('פיילוט פג בקרוב', 'Trial expiring soon'), value: expiringSoon, color: expiringSoon > 0 ? 'text-amber-600' : 'text-gray-400' },
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
            <p className="text-sm font-medium text-gray-700">{tt('פעילות אחרונה', 'Recent activity')}</p>
            <Link to="/admin/audit" className="text-xs text-moca-bolt hover:underline">{tt('כל הרשומות ←', 'All records ←')}</Link>
          </div>
          <div className="space-y-1.5">
            {recentEvents.map(e => (
              <div key={e.id} className="flex items-center gap-3 text-xs text-gray-600">
                <span className="text-gray-400 whitespace-nowrap">
                  {e.created_at ? new Date(e.created_at).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' }) : '-'}
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
  const { tt } = useLang()
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
          primary_color:     form.primary_color || null,
          secondary_color:   form.secondary_color || null,
          app_title:         form.app_title || null,
          logo_url:          form.logo_url || null,
          slack_webhook_url: form.slack_webhook_url || null,
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
      <div className="flex items-center justify-between mb-6 gap-4">
        <p className="text-sm text-gray-600 flex-1">
          {tt('כל workspace הוא לקוח MVNO נפרד עם צבעי מותג, feature flags וסינון ספקים משלו.', 'Each workspace is a separate MVNO client with its own brand colors, feature flags and carrier filtering.')}
        </p>
        <Button onClick={() => setCreating(c => !c)} variant="primary">
          {creating ? tt('סגור', 'Close') : tt('+ workspace חדש', '+ New workspace')}
        </Button>
      </div>

      {!loading && !error && <StatsBar list={list} recentEvents={recentEvents} />}

      {creating && (
        <form onSubmit={create}
          className="bg-moca-cream border border-moca-border rounded-xl p-5 mb-6 space-y-3">
          <h3 className="font-semibold">{tt('יצירת workspace', 'Create workspace')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">{tt('Slug (מזהה URL) *', 'Slug (URL identifier) *')}</span>
              <input required pattern="[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?"
                value={form.slug}
                onChange={e => setForm({...form, slug: e.target.value.toLowerCase()})}
                placeholder="partner-pilot"
                className="w-full px-3 py-1.5 border border-moca-border rounded" />
            </label>
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">{tt('שם תצוגה *', 'Display name *')}</span>
              <input required value={form.name}
                onChange={e => setForm({...form, name: e.target.value})}
                placeholder="Partner Intelligence"
                className="w-full px-3 py-1.5 border border-moca-border rounded" />
            </label>
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">{tt('MVNO של הלקוח', "Client's MVNO")}</span>
              <select value={form.mvno_carrier}
                onChange={e => setForm(withMvnoColors(form, e.target.value))}
                className="w-full px-3 py-1.5 border border-moca-border rounded">
                {MVNO_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.en ? tt(o.label, o.en) : o.label}</option>)}
              </select>
            </label>
            <label className="text-sm flex items-end gap-2 cursor-pointer">
              <input type="checkbox" checked={form.hide_self_carrier}
                onChange={e => setForm({...form, hide_self_carrier: e.target.checked})} />
              <span>{tt('הסתר ספק עצמי מהתוצאות', 'Hide self carrier from results')}</span>
            </label>
            <ColorInput label={tt('צבע ראשי (primary)', 'Primary color')} value={form.primary_color}
              defaultColor={getMvnoColors(form.mvno_carrier)?.primary}
              defaultLabel={MVNO_OPTIONS.find(o => o.id === form.mvno_carrier)?.label}
              onChange={v => setForm({...form, primary_color: v})} />
            <ColorInput label={tt('צבע משני (secondary)', 'Secondary color')} value={form.secondary_color}
              defaultColor={getMvnoColors(form.mvno_carrier)?.secondary}
              defaultLabel={MVNO_OPTIONS.find(o => o.id === form.mvno_carrier)?.label}
              onChange={v => setForm({...form, secondary_color: v})} />
            <label className="text-sm">
              <span className="block mb-1 text-gray-700">{tt('כותרת האפליקציה', 'App title')}</span>
              <input type="text" value={form.app_title}
                onChange={e => setForm({...form, app_title: e.target.value})}
                placeholder="Partner Intelligence"
                className="w-full px-3 py-1.5 border border-moca-border rounded" />
            </label>
            <div className="text-sm">
              <span className="block mb-1 text-gray-700">{tt('לוגו', 'Logo')}</span>
              <LogoField value={form.logo_url}
                onChange={v => setForm({...form, logo_url: v})} />
            </div>
          </div>
          {createError && <p className="text-sm text-red-600">{createError}</p>}
          <div className="flex gap-2">
            <Button type="submit" disabled={submitting} variant="primary">
              {submitting ? tt('יוצר…', 'Creating…') : tt('צור', 'Create')}
            </Button>
            <Button type="button" onClick={() => setCreating(false)} variant="ghost">{tt('ביטול', 'Cancel')}</Button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">{tt('טוען…', 'Loading…')}</p>
      ) : error ? (
        <p className="text-red-600">{tt('שגיאה:', 'Error:')} {error}</p>
      ) : (
        <div className="space-y-3">
          {list.map(ws => <WorkspaceRow key={ws.id} ws={ws} onChange={load} />)}
        </div>
      )}
    </div>
  )
}
