import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useLang } from '../hooks/useLanguage'
import { api } from '../lib/api'
import { FLAG_FOR_PATH, NAV_GROUPS, NAV_SECTIONS } from '../data/navFlags'
import { DOMESTIC_LABELS, GLOBAL_PROVIDERS, carrierLabel } from '../data/carrierLabels'
import Spinner from '../components/ui/Spinner'
import { SETUP_CHECKED_KEY } from '../components/SetupPrompt'

/**
 * Dashboard setup wizard (/setup).
 *
 * Two kinds of answers, saved separately (api/setup.py):
 *  - WORKSPACE level, asked only of the workspace's admin: which sections to
 *    show / emphasize / hide, the landing page, the competitors in focus.
 *  - USER level, asked of everyone: what to be alerted about, through which
 *    channel (e-mail / WhatsApp), to which address or number, how often, and
 *    on which days and hours.
 *
 * Opens by itself on a user's first login (components/SetupPrompt.jsx sends
 * them here with ?welcome=1) and stays reachable from the profile menu.
 */

// Mirrors DEFAULT_USER_CONFIG in dashboard_setup.py (used until the server answers).
const DEFAULT_USER = {
  role: 'other',
  channels: {
    email:    { enabled: true,  address: '', frequency: 'daily' },
    whatsapp: { enabled: false, phone: '',   frequency: 'immediate' },
  },
  categories: ['domestic', 'abroad'],
  events: ['price_drop', 'price_rise', 'new_plan', 'removed_plan'],
  min_price_delta: 1,
  carrier_scope: 'all',
  quiet: { days: [0, 1, 2, 3, 4], from: '08:00', to: '20:00' },
  lang: 'he',
}

const ROLES = [
  { id: 'marketing',  he: 'שיווק',            en: 'Marketing',
    desc: { he: 'קמפיינים, באנרים ומסרים של המתחרים', en: 'Competitor campaigns, banners and messaging' } },
  { id: 'pricing',    he: 'תמחור ומוצר',      en: 'Pricing & product',
    desc: { he: 'מחירים, חבילות ומיצוב מול השוק', en: 'Prices, plans and market positioning' } },
  { id: 'sales',      he: 'מכירות ושירות',    en: 'Sales & care',
    desc: { he: 'מענה מהיר מול לקוח שמצטט מתחרה', en: 'Fast answers when a customer quotes a competitor' } },
  { id: 'management', he: 'הנהלה',            en: 'Management',
    desc: { he: 'תמונת מצב תמציתית, בלי רעש', en: 'A concise picture without the noise' } },
  { id: 'other',      he: 'אחר',              en: 'Other',
    desc: { he: 'אבחר הכול בעצמי', en: 'I will choose everything myself' } },
]

// Starting points per role - applied only on a first run, and only to answers
// the user has not saved before. Everything stays editable in the later steps.
const ROLE_PRESETS = {
  marketing:  { focus: ['/banners', '/news', '/social', '/plans'], categories: ['domestic', 'abroad', 'resellers'],
                events: ['price_drop', 'price_rise', 'new_plan', 'removed_plan', 'terms_change'], email: 'daily' },
  pricing:    { focus: ['/plans', '/compare', '/history', '/positioning'], categories: ['domestic', 'abroad'],
                events: ['price_drop', 'price_rise', 'new_plan', 'removed_plan'], email: 'immediate' },
  sales:      { focus: ['/agent-desk', '/plans', '/resellers'], categories: ['domestic', 'resellers'],
                events: ['price_drop', 'new_plan'], email: 'daily' },
  management: { focus: ['/cockpit', '/executive-summary'], categories: ['domestic'],
                events: ['price_drop', 'price_rise', 'new_plan'], email: 'weekly' },
}

const CATEGORIES = [
  { id: 'domestic',  path: '/plans',     he: 'חבילות סלולר',       en: 'Mobile plans' },
  { id: 'abroad',    path: '/roaming',   he: 'חבילות חו״ל',        en: 'Roaming' },
  { id: 'global',    path: '/esim',      he: 'eSIM גלובלי',        en: 'Global eSIM' },
  { id: 'content',   path: '/content',   he: 'שירותי תוכן',        en: 'Content services' },
  { id: 'resellers', path: '/resellers', he: 'משווקים (מתחת לקו)', en: 'Resellers (below the line)' },
]

const EVENTS = [
  { id: 'price_drop',   he: 'ירידת מחיר',      en: 'Price drop',
    desc: { he: 'מתחרה הוזיל חבילה', en: 'A competitor cut a price' } },
  { id: 'price_rise',   he: 'עליית מחיר',      en: 'Price rise',
    desc: { he: 'מתחרה ייקר חבילה', en: 'A competitor raised a price' } },
  { id: 'new_plan',     he: 'חבילה חדשה',      en: 'New plan',
    desc: { he: 'השקה של חבילה או מבצע', en: 'A plan or promotion was launched' } },
  { id: 'removed_plan', he: 'חבילה שהוסרה',    en: 'Plan removed',
    desc: { he: 'חבילה ירדה מהמדף', en: 'A plan left the shelf' } },
  { id: 'terms_change', he: 'שינוי תנאים',     en: 'Terms change',
    desc: { he: 'הטבות, נפח או תנאים השתנו', en: 'Benefits, volume or terms changed' } },
]

const DELTAS = [
  { v: 0,  he: 'כל שינוי',      en: 'Any change' },
  { v: 1,  he: 'מ-1 ₪ ומעלה',   en: '₪1 and up' },
  { v: 5,  he: 'מ-5 ₪ ומעלה',   en: '₪5 and up' },
  { v: 10, he: 'מ-10 ₪ ומעלה',  en: '₪10 and up' },
]

const FREQS = [
  { v: 'immediate', he: 'שוטף',  en: 'Live',
    desc: { he: 'זמן קצר אחרי כל סריקה (בוקר ואחר הצהריים)', en: 'Shortly after each scan (morning and afternoon)' } },
  { v: 'daily',     he: 'יומי',  en: 'Daily',
    desc: { he: 'סיכום אחד ביום, בבוקר', en: 'One summary a day, in the morning' } },
  { v: 'weekly',    he: 'שבועי', en: 'Weekly',
    desc: { he: 'סיכום אחד בתחילת השבוע', en: 'One summary at the start of the week' } },
]

const DAYS_HE = ['א׳', 'ב׳', 'ג׳', 'ד׳', 'ה׳', 'ו׳', 'ש׳']
const DAYS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const RE_EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/
const validPhone = (raw) => {
  let d = String(raw || '').replace(/\D/g, '')
  if (d.startsWith('00')) d = d.slice(2)
  if (d.startsWith('0')) d = '972' + d.slice(1)
  return /^\d{10,15}$/.test(d)
}

// ─── Small building blocks ──────────────────────────────────────────────────

function Chip({ pressed, onClick, children, disabled }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      className={`px-3.5 py-2 rounded-full text-[13.5px] border transition-colors disabled:opacity-45 disabled:cursor-not-allowed ${
        pressed
          ? 'bg-moca-bolt text-white border-moca-bolt font-semibold'
          : 'bg-white text-moca-text border-moca-border hover:bg-moca-cream'
      }`}
    >
      {children}
    </button>
  )
}

function Seg({ value, onChange, options, label }) {
  return (
    <div role="group" aria-label={label} className="inline-flex self-start sm:self-auto rounded-full border border-moca-border bg-moca-cream p-0.5 shrink-0">
      {options.map(o => (
        <button
          key={String(o.value)}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 rounded-full text-[12.5px] transition-colors ${
            value === o.value ? 'bg-moca-bolt text-white font-semibold' : 'text-moca-text hover:bg-white'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function Question({ title, hint, children }) {
  return (
    <section className="mb-7 last:mb-0">
      <h3 className="text-[15px] font-bold text-moca-text">{title}</h3>
      {hint && <p className="text-[13px] text-moca-sub mt-0.5 mb-3">{hint}</p>}
      {!hint && <div className="mb-3" />}
      {children}
    </section>
  )
}

function Toggle({ checked, onChange, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${checked ? 'bg-moca-bolt' : 'bg-moca-sand'}`}
    >
      <span
        className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all"
        style={{ insetInlineStart: checked ? 22 : 2 }}
      />
    </button>
  )
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default function SetupWizardPage() {
  const { user, workspace, isAdmin, viewAs, retryContext } = useAuth()
  const { tt, lang } = useLang()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const welcome = params.get('welcome') === '1'

  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [meta, setMeta] = useState(null)
  const [ws, setWs] = useState({ sections: {}, landing: '', focus_carriers: [] })
  const [prefs, setPrefs] = useState(DEFAULT_USER)
  const [stepIdx, setStepIdx] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const [presetApplied, setPresetApplied] = useState(false)
  const [testState, setTestState] = useState({})
  const [confirmReset, setConfirmReset] = useState(null)   // null | 'user' | 'workspace'
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState(null)
  const headingRef = useRef(null)

  const load = () => {
    setLoading(true)
    api.getDashboardSetup()
      .then(data => {
        setMeta(data)
        setLoadFailed(false)
        const w = data.workspace?.config || {}
        setWs({ sections: w.sections || {}, landing: w.landing || '', focus_carriers: w.focus_carriers || [] })
        const saved = data.user?.config || {}
        const base = data.defaults || DEFAULT_USER
        const merged = {
          ...base, ...saved,
          channels: {
            email:    { ...base.channels.email,    ...(saved.channels?.email || {}) },
            whatsapp: { ...base.channels.whatsapp, ...(saved.channels?.whatsapp || {}) },
          },
          quiet: { ...base.quiet, ...(saved.quiet || {}) },
        }
        if (!merged.channels.email.address) merged.channels.email.address = data.user?.email || ''
        if (!data.user?.completed_at) merged.lang = lang === 'en' ? 'en' : 'he'
        setPrefs(merged)
      })
      .catch(() => {
        // Saved answers could not be loaded: still show the wizard on defaults
        // (saving will report the real problem) rather than a dead page.
        setLoadFailed(true)
        setMeta({
          can_edit_workspace: isAdmin,
          workspace: {
            mvno_carrier: workspace?.mvno_carrier, hide_self_carrier: workspace?.hide_self_carrier,
            visible_carriers: workspace?.visible_carriers || [], locked_flags: workspace?.feature_flags || {},
            config: workspace?.dashboard_config || {},
          },
          user: { email: user?.email || '', config: {} },
        })
        setPrefs(p => ({ ...p, channels: { ...p.channels, email: { ...p.channels.email, address: user?.email || '' } } }))
      })
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [])

  const canEditWs = !!meta?.can_edit_workspace
  const locked = useMemo(() => meta?.workspace?.locked_flags || {}, [meta])
  const available = useMemo(() => NAV_SECTIONS.filter(s => !locked[FLAG_FOR_PATH[s.path]]), [locked])
  const visiblePaths = useMemo(
    () => available.filter(s => ws.sections[s.path] !== 'hidden').map(s => s.path),
    [available, ws.sections])
  const shownCategories = CATEGORIES.filter(c => visiblePaths.includes(c.path))

  const selfCarrier = meta?.workspace?.mvno_carrier || null
  const domesticCarriers = useMemo(() => {
    const allow = meta?.workspace?.visible_carriers || []
    return Object.keys(DOMESTIC_LABELS)
      .filter(id => (allow.length ? allow.includes(id) : true))
      .filter(id => !(meta?.workspace?.hide_self_carrier && id === selfCarrier))
  }, [meta, selfCarrier])

  const steps = useMemo(() => [
    { id: 'role',        he: 'תפקיד ומטרה',           en: 'Role & goal',        short: { he: 'תפקיד', en: 'Role' } },
    canEditWs && { id: 'sections',    he: 'מה להציג ומה להדגיש',   en: 'What to show',       short: { he: 'תצוגה', en: 'Display' } },
    canEditWs && { id: 'competitors', he: 'מתחרים במוקד',          en: 'Focus competitors',  short: { he: 'מתחרים', en: 'Competitors' } },
    { id: 'events',      he: 'על מה להתריע',          en: 'What to alert on',   short: { he: 'התראות', en: 'Alerts' } },
    { id: 'channels',    he: 'לאן ובאיזו תדירות',     en: 'Where & how often',  short: { he: 'ערוצים', en: 'Channels' } },
    { id: 'schedule',    he: 'מתי לשלוח',             en: 'When to send',       short: { he: 'תזמון', en: 'Timing' } },
    { id: 'review',      he: 'סיכום',                 en: 'Review',             short: { he: 'סיכום', en: 'Review' } },
  ].filter(Boolean), [canEditWs])
  const step = steps[Math.min(stepIdx, steps.length - 1)]

  // Move focus to the step heading on every step change (keyboard + screen readers).
  useEffect(() => {
    if (loading) return
    headingRef.current?.focus({ preventScroll: true })
    document.querySelector('main')?.scrollTo?.({ top: 0 })
  }, [stepIdx, loading])

  // ── state helpers ──
  const patch = (obj) => setPrefs(p => ({ ...p, ...obj }))
  const patchChannel = (ch, obj) =>
    setPrefs(p => ({ ...p, channels: { ...p.channels, [ch]: { ...p.channels[ch], ...obj } } }))
  const toggleIn = (key, id) =>
    setPrefs(p => ({ ...p, [key]: p[key].includes(id) ? p[key].filter(x => x !== id) : [...p[key], id] }))
  const setSection = (path, state) => setWs(w => {
    const sections = { ...w.sections }
    if (state === 'normal') delete sections[path]
    else sections[path] = state
    return { ...w, sections, landing: state === 'hidden' && w.landing === path ? '' : w.landing }
  })
  const toggleFocusCarrier = (id) => setWs(w => ({
    ...w,
    focus_carriers: w.focus_carriers.includes(id) ? w.focus_carriers.filter(x => x !== id) : [...w.focus_carriers, id],
  }))

  const chooseRole = (id) => {
    patch({ role: id })
    const preset = ROLE_PRESETS[id]
    let applied = false
    if (preset && !meta?.user?.completed_at) {
      setPrefs(p => ({
        ...p, role: id, categories: preset.categories, events: preset.events,
        channels: { ...p.channels, email: { ...p.channels.email, frequency: preset.email } },
      }))
      applied = true
    }
    if (preset && canEditWs && !meta?.workspace?.completed_at) {
      setWs(w => {
        const sections = Object.fromEntries(Object.entries(w.sections).filter(([, s]) => s !== 'focus'))
        preset.focus.forEach(p => { if (!locked[FLAG_FOR_PATH[p]] && sections[p] !== 'hidden') sections[p] = 'focus' })
        return { ...w, sections }
      })
      applied = true
    }
    setPresetApplied(applied)
  }

  const errText = (msg) => ({
    'bad phone': tt('מספר הטלפון אינו תקין. יש להזין מספר נייד מלא, למשל 054-1234567.', 'The phone number is not valid. Enter a full mobile number.'),
    'bad email': tt('כתובת המייל אינה תקינה.', 'The e-mail address is not valid.'),
    'at least one section must stay visible': tt('חייב להישאר לפחות סעיף אחד מוצג.', 'At least one section must stay visible.'),
    'send failed': tt('השליחה נכשלה. בדקו את הפרטים ונסו שוב.', 'Sending failed. Check the details and try again.'),
    'auth required': tt('לא ניתן לזהות את המשתמש. התחברו מחדש ונסו שוב.', 'Could not identify the user. Sign in again and retry.'),
  }[msg] || msg || tt('אירעה שגיאה. נסו שוב.', 'Something went wrong. Try again.'))

  const channelProblem = () => {
    const { email, whatsapp } = prefs.channels
    if (email.enabled && !RE_EMAIL.test(email.address || '')) return 'bad email'
    if (whatsapp.enabled && !validPhone(whatsapp.phone)) return 'bad phone'
    return null
  }

  const goNext = () => {
    setError(null)
    if (step.id === 'channels') {
      const problem = channelProblem()
      if (problem) { setError(errText(problem)); return }
    }
    setStepIdx(i => Math.min(i + 1, steps.length - 1))
  }
  const goBack = () => { setError(null); setStepIdx(i => Math.max(i - 1, 0)) }
  const goTo = (id) => { setError(null); setStepIdx(Math.max(0, steps.findIndex(s => s.id === id))) }

  const sendTest = async (channel) => {
    setTestState(s => ({ ...s, [channel]: 'sending' }))
    try {
      await api.testDashboardChannel({
        channel, lang: prefs.lang,
        address: prefs.channels.email.address, phone: prefs.channels.whatsapp.phone,
      })
      setTestState(s => ({ ...s, [channel]: 'sent' }))
    } catch (e) {
      setTestState(s => ({ ...s, [channel]: errText(e.message) }))
    }
  }

  const save = async () => {
    const problem = channelProblem()
    if (problem) { goTo('channels'); setError(errText(problem)); return }
    setSaving(true); setError(null)
    try {
      if (canEditWs) await api.saveDashboardSetupWorkspace(ws)
      // Never alert on a category whose section is hidden.
      await api.saveDashboardSetupUser({
        ...prefs, categories: prefs.categories.filter(c => shownCategories.some(s => s.id === c)),
      })
      try { sessionStorage.setItem(SETUP_CHECKED_KEY, user?.id || '') } catch { /* ignore */ }
      await retryContext?.()
      setDone(true)
    } catch (e) {
      setError(errText(e.message))
    } finally {
      setSaving(false)
    }
  }

  const skip = async () => {
    try { await api.dismissDashboardSetup() } catch { /* the prompt may show once more */ }
    try { sessionStorage.setItem(SETUP_CHECKED_KEY, user?.id || '') } catch { /* ignore */ }
    navigate('/home', { replace: true })
  }

  // Reset: erase saved answers. The server keeps a "dismissed" marker for a
  // personal reset, so the first-login prompt does not come back.
  const hasUserSetup = !loadFailed && !!meta?.user?.completed_at
  const hasWsSetup = !loadFailed && canEditWs && !!meta?.workspace?.completed_at
  const doReset = async (kind) => {
    setResetting(true)
    try {
      if (kind === 'workspace') {
        await api.resetDashboardSetupWorkspace()
        await retryContext?.()
      } else {
        await api.resetDashboardSetupUser()
      }
      setResetMsg({
        ok: true,
        text: kind === 'workspace'
          ? tt('תצוגת הארגון אופסה לברירת המחדל.', 'The organization view was reset to the default.')
          : tt('ההתראות האישיות אופסו, והפרטים נמחקו.', 'Your personal alerts were reset and the details deleted.'),
      })
      setStepIdx(0)
      setPresetApplied(false)
      setTestState({})
      load()
    } catch (e) {
      setResetMsg({ ok: false, text: errText(e.message) })
    } finally {
      setResetting(false)
      setConfirmReset(null)
    }
  }

  const finish = () => {
    const target = canEditWs && ws.landing && ws.landing !== '/' ? ws.landing : '/home'
    try { sessionStorage.setItem('moca_landed', '1') } catch { /* ignore */ }
    navigate(target, { replace: true })
  }

  const sectionLabel = (s) => (s.wizard ? tt(s.wizard.he, s.wizard.en) : tt(s.he, s.en))
  const label = (list, id) => { const x = list.find(i => (i.id ?? i.v) === id); return x ? tt(x.he, x.en) : id }

  // ── render ──
  if (viewAs) {
    return (
      <div className="max-w-xl mx-auto p-6">
        <div className="bg-white border border-moca-border/60 rounded-2xl p-6 text-[14px] text-moca-text">
          {tt('במצב "צופה כ" לא ניתן לערוך את ההתאמה האישית. צאו מהמצב כדי לערוך את ההגדרות שלכם.',
              'Personalization cannot be edited while viewing as a workspace. Exit view-as to edit your own settings.')}
        </div>
      </div>
    )
  }
  if (loading) return <div className="flex justify-center py-20"><Spinner /></div>

  if (done) {
    const anyChannel = prefs.channels.email.enabled || prefs.channels.whatsapp.enabled
    return (
      <div className="max-w-xl mx-auto p-4 md:p-8">
        <div className="bg-white border border-moca-border/60 rounded-2xl p-7 text-center">
          <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-moca-cream text-moca-down flex items-center justify-center" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          </div>
          <h2 className="text-[19px] font-bold text-moca-text" role="status">{tt('ההגדרות נשמרו', 'Settings saved')}</h2>
          <p className="text-[14px] text-moca-sub mt-2 mb-6">
            {anyChannel
              ? tt('הדשבורד מותאם, וההתראות יישלחו לפי מה שנבחר. אפשר לשנות בכל רגע מתפריט הפרופיל, תחת "התאמה אישית".',
                   'Your dashboard is set and alerts will be sent as chosen. Change anything any time from the profile menu, under "Personalize".')
              : tt('הדשבורד מותאם. לא נבחר ערוץ התראות, ולכן לא יישלחו הודעות. אפשר להוסיף ערוץ בכל רגע מתפריט הפרופיל, תחת "התאמה אישית".',
                   'Your dashboard is set. No alert channel was chosen, so no messages will be sent. Add one any time from the profile menu, under "Personalize".')}
          </p>
          <button type="button" onClick={finish} className="px-7 py-2.5 rounded-full bg-moca-bolt text-white text-[14px] font-bold hover:opacity-90">
            {tt('לדשבורד', 'Go to the dashboard')}
          </button>
        </div>
      </div>
    )
  }

  const last = stepIdx === steps.length - 1

  return (
    <div className="max-w-3xl mx-auto p-4 md:p-8">
      {welcome && stepIdx === 0 && (
        <div className="mb-5">
          <h2 className="text-[22px] font-bold text-moca-text">{tt('ברוכים הבאים ל-MOCA', 'Welcome to MOCA')}</h2>
          <p className="text-[14px] text-moca-sub mt-1">
            {tt('כמה שאלות קצרות, ונתאים את הדשבורד וההתראות לצרכים שלכם. אפשר לדלג ולחזור לזה אחר כך.',
                'A few short questions and the dashboard and alerts will fit your needs. You can skip and come back later.')}
          </p>
        </div>
      )}

      {loadFailed && (
        <div role="alert" className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-moca-up/40 bg-white px-4 py-3 text-[13px] text-moca-text">
          <span>{tt('לא ניתן היה לטעון הגדרות שמורות. מוצגות ברירות המחדל.', 'Saved settings could not be loaded. Showing the defaults.')}</span>
          <button type="button" onClick={load} className="font-semibold text-moca-bolt underline shrink-0">{tt('נסו שוב', 'Retry')}</button>
        </div>
      )}

      {/* Progress */}
      <nav aria-label={tt('שלבי ההתאמה', 'Setup steps')} className="mb-4">
        <p className="md:hidden text-[12.5px] text-moca-sub mb-2">
          {tt(`שלב ${stepIdx + 1} מתוך ${steps.length}`, `Step ${stepIdx + 1} of ${steps.length}`)}
        </p>
        <ol className="flex gap-1.5">
          {steps.map((s, i) => (
            <li key={s.id} className="flex-1 min-w-0">
              <button
                type="button"
                onClick={() => goTo(s.id)}
                aria-current={i === stepIdx ? 'step' : undefined}
                aria-label={tt(s.he, s.en)}
                className="w-full text-start group"
              >
                <span className={`block h-1.5 rounded-full transition-colors ${i <= stepIdx ? 'bg-moca-bolt' : 'bg-moca-sand'}`} />
                <span className={`hidden md:block mt-1.5 text-[11.5px] truncate ${i === stepIdx ? 'text-moca-text font-bold' : 'text-moca-sub group-hover:text-moca-text'}`}>
                  {tt(s.short.he, s.short.en)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <div className="bg-white border border-moca-border/60 rounded-2xl p-5 md:p-7">
        <h2 ref={headingRef} tabIndex={-1} className="text-[19px] font-bold text-moca-text mb-5 outline-none">
          {tt(step.he, step.en)}
        </h2>

        {/* ── 1. Role ── */}
        {step.id === 'role' && (
          <Question
            title={tt('במה אתם עוסקים?', 'What do you do?')}
            hint={tt('לפי הבחירה נציע נקודת פתיחה מתאימה. כל הצעה ניתנת לשינוי בשלבים הבאים.', 'We suggest a starting point based on your choice. Every suggestion can be changed in the next steps.')}
          >
            <div className="grid gap-2 sm:grid-cols-2">
              {ROLES.map(r => (
                <button
                  key={r.id}
                  type="button"
                  aria-pressed={prefs.role === r.id}
                  onClick={() => chooseRole(r.id)}
                  className={`text-start rounded-xl border px-4 py-3 transition-colors ${
                    prefs.role === r.id ? 'border-moca-bolt bg-moca-cream' : 'border-moca-border bg-white hover:bg-moca-mist'
                  }`}
                >
                  <span className="block text-[14.5px] font-bold text-moca-text">{tt(r.he, r.en)}</span>
                  <span className="block text-[12.5px] text-moca-sub mt-0.5">{tt(r.desc.he, r.desc.en)}</span>
                </button>
              ))}
            </div>
            {/* Always rendered (fixed height) so the buttons below never jump */}
            <p role="status" className="mt-3 text-[13px] text-moca-sub min-h-[20px]">
              {presetApplied && tt('עדכנו את ההצעות בשלבים הבאים לפי התפקיד שנבחר.', 'The suggestions in the next steps were updated for this role.')}
            </p>
          </Question>
        )}

        {/* ── 2. Sections ── */}
        {step.id === 'sections' && (
          <>
            <p className="text-[13px] text-moca-sub -mt-3 mb-5">
              {tt('הבחירה חלה על כל המשתמשים בארגון. סעיף "במוקד" מוצמד לראש התפריט, וסעיף "מוסתר" לא יופיע בו.',
                  'This applies to everyone in your organization. A "Focus" section is pinned to the top of the menu; a "Hidden" one is removed from it.')}
            </p>
            {NAV_GROUPS.map(g => {
              const rows = available.filter(s => s.group === g.key)
              if (!rows.length) return null
              return (
                <section key={g.key} className="mb-6">
                  <h3 className="text-[12px] font-bold text-moca-sub tracking-wide mb-1">{tt(g.he, g.en)}</h3>
                  <ul className="divide-y divide-moca-border/50">
                    {rows.map(s => {
                      const state = ws.sections[s.path] || 'normal'
                      const lastVisible = state !== 'hidden' && visiblePaths.length === 1
                      return (
                        <li key={s.path} className="py-2.5 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                          <div className="flex-1 min-w-0">
                            <div className={`text-[14px] font-semibold ${state === 'hidden' ? 'text-moca-muted line-through' : 'text-moca-text'}`}>{sectionLabel(s)}</div>
                            <div className="text-[12.5px] text-moca-sub">{tt(s.desc.he, s.desc.en)}</div>
                          </div>
                          <Seg
                            label={sectionLabel(s)}
                            value={state}
                            onChange={(v) => { if (v === 'hidden' && lastVisible) return; setSection(s.path, v) }}
                            options={[
                              { value: 'focus',  label: tt('במוקד', 'Focus') },
                              { value: 'normal', label: tt('רגיל', 'Normal') },
                              { value: 'hidden', label: tt('מוסתר', 'Hidden') },
                            ]}
                          />
                        </li>
                      )
                    })}
                  </ul>
                </section>
              )
            })}
            <Question
              title={tt('עמוד הפתיחה', 'Landing page')}
              hint={tt('העמוד שייפתח מיד אחרי הכניסה למערכת.', 'The page that opens right after signing in.')}
            >
              <select
                value={visiblePaths.includes(ws.landing) ? ws.landing : ''}
                onChange={e => setWs(w => ({ ...w, landing: e.target.value }))}
                aria-label={tt('עמוד הפתיחה', 'Landing page')}
                className="w-full sm:w-80 rounded-lg border border-moca-border bg-white px-3 py-2 text-[14px] text-moca-text"
              >
                <option value="">{tt('ברירת המחדל (דשבורד)', 'Default (dashboard)')}</option>
                {available.filter(s => visiblePaths.includes(s.path) && s.path !== '/').map(s => (
                  <option key={s.path} value={s.path}>{sectionLabel(s)}</option>
                ))}
              </select>
            </Question>
          </>
        )}

        {/* ── 3. Competitors ── */}
        {step.id === 'competitors' && (
          <>
            {selfCarrier && (
              <p className="text-[13.5px] text-moca-text -mt-2 mb-5">
                {tt('המפעיל שלכם במערכת: ', 'Your carrier in the system: ')}
                <strong>{carrierLabel(selfCarrier)}</strong>
              </p>
            )}
            <Question
              title={tt('אילו מתחרים הכי חשובים לכם?', 'Which competitors matter most?')}
              hint={tt('מתחרים במוקד מופיעים ראשונים ברשימות ובהתראות. אפשר לבחור כמה שרוצים, או לא לבחור בכלל.',
                       'Focus competitors come first in lists and alerts. Choose as many as you like, or none.')}
            >
              <div className="flex flex-wrap gap-2">
                {domesticCarriers.map(id => (
                  <Chip key={id} pressed={ws.focus_carriers.includes(id)} onClick={() => toggleFocusCarrier(id)}>
                    {carrierLabel(id)}
                  </Chip>
                ))}
              </div>
            </Question>
            {visiblePaths.includes('/esim') && (
              <details className="rounded-xl border border-moca-border/70 px-4 py-3">
                <summary className="cursor-pointer text-[14px] font-semibold text-moca-text">
                  {tt('ספקי eSIM גלובליים במוקד', 'Focus global eSIM providers')}
                  {ws.focus_carriers.some(c => GLOBAL_PROVIDERS.some(p => p.id === c)) && (
                    <span className="text-moca-sub font-normal"> · {ws.focus_carriers.filter(c => GLOBAL_PROVIDERS.some(p => p.id === c)).length}</span>
                  )}
                </summary>
                <div className="flex flex-wrap gap-2 mt-3">
                  {GLOBAL_PROVIDERS.map(p => (
                    <Chip key={p.id} pressed={ws.focus_carriers.includes(p.id)} onClick={() => toggleFocusCarrier(p.id)}>
                      {p.label}
                    </Chip>
                  ))}
                </div>
              </details>
            )}
          </>
        )}

        {/* ── 4. What to alert on ── */}
        {step.id === 'events' && (
          <>
            <Question title={tt('באילו תחומים?', 'Which areas?')}>
              <div className="flex flex-wrap gap-2">
                {shownCategories.map(c => (
                  <Chip key={c.id} pressed={prefs.categories.includes(c.id)} onClick={() => toggleIn('categories', c.id)}>
                    {tt(c.he, c.en)}
                  </Chip>
                ))}
              </div>
              {prefs.categories.includes('global') && shownCategories.some(c => c.id === 'global') && (
                <p className="mt-2 text-[12.5px] text-moca-sub">
                  {tt('בתחום ה-eSIM הגלובלי יש עשרות עדכוני מחיר ביום. מומלץ לשלב אותו עם סף מחיר או עם "רק מתחרים במוקד".',
                      'Global eSIM sees dozens of price updates a day. Pair it with a price threshold or with "focus competitors only".')}
                </p>
              )}
            </Question>
            <Question title={tt('אילו אירועים?', 'Which events?')}>
              <div className="grid gap-2 sm:grid-cols-2">
                {EVENTS.map(ev => {
                  const on = prefs.events.includes(ev.id)
                  return (
                    <button
                      key={ev.id}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggleIn('events', ev.id)}
                      className={`text-start rounded-xl border px-4 py-2.5 transition-colors ${on ? 'border-moca-bolt bg-moca-cream' : 'border-moca-border bg-white hover:bg-moca-mist'}`}
                    >
                      <span className="block text-[14px] font-bold text-moca-text">{tt(ev.he, ev.en)}</span>
                      <span className="block text-[12.5px] text-moca-sub">{tt(ev.desc.he, ev.desc.en)}</span>
                    </button>
                  )
                })}
              </div>
            </Question>
            <Question
              title={tt('מאיזה שינוי מחיר להתריע?', 'How big a price move?')}
              hint={tt('שינויים קטנים מהסף לא יישלחו. הם עדיין מופיעים בדשבורד.', 'Moves below the threshold are not sent. They still appear on the dashboard.')}
            >
              <div className="flex flex-wrap gap-2">
                {DELTAS.map(d => (
                  <Chip key={d.v} pressed={Number(prefs.min_price_delta) === d.v} onClick={() => patch({ min_price_delta: d.v })}>
                    {tt(d.he, d.en)}
                  </Chip>
                ))}
              </div>
            </Question>
            <Question title={tt('על אילו מתחרים?', 'Which competitors?')}>
              <div className="flex flex-wrap gap-2">
                <Chip pressed={prefs.carrier_scope !== 'focus'} onClick={() => patch({ carrier_scope: 'all' })}>
                  {tt('כל המתחרים', 'All competitors')}
                </Chip>
                <Chip
                  pressed={prefs.carrier_scope === 'focus'}
                  disabled={ws.focus_carriers.length === 0}
                  onClick={() => patch({ carrier_scope: 'focus' })}
                >
                  {tt('רק מתחרים במוקד', 'Focus competitors only')}
                </Chip>
              </div>
              <p className="mt-2 text-[12.5px] text-moca-sub">
                {ws.focus_carriers.length
                  ? tt('במוקד: ', 'In focus: ') + ws.focus_carriers.map(carrierLabel).join(', ')
                  : canEditWs
                    ? tt('לא נבחרו מתחרים במוקד. אפשר לבחור בשלב "מתחרים במוקד".', 'No focus competitors chosen. Pick them in the "Focus competitors" step.')
                    : tt('מנהל הארגון עוד לא בחר מתחרים במוקד.', 'Your organization admin has not chosen focus competitors yet.')}
              </p>
            </Question>
          </>
        )}

        {/* ── 5. Channels ── */}
        {step.id === 'channels' && (
          <>
            {[
              { ch: 'email', title: tt('מייל', 'E-mail'), field: 'address', type: 'email', inputMode: 'email',
                fieldLabel: tt('כתובת המייל לקבלת ההתראות', 'E-mail address for alerts'), placeholder: 'name@company.co.il',
                ok: RE_EMAIL.test(prefs.channels.email.address || '') },
              { ch: 'whatsapp', title: 'WhatsApp', field: 'phone', type: 'tel', inputMode: 'tel',
                fieldLabel: tt('מספר הנייד לקבלת ההתראות', 'Mobile number for alerts'), placeholder: '054-1234567',
                ok: validPhone(prefs.channels.whatsapp.phone) },
            ].map(({ ch, title, field, type, inputMode, fieldLabel, placeholder, ok }) => {
              const c = prefs.channels[ch]
              const t = testState[ch]
              return (
                <section key={ch} className={`rounded-xl border px-4 py-4 mb-4 ${c.enabled ? 'border-moca-bolt/60' : 'border-moca-border/70'}`}>
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-[15px] font-bold text-moca-text">{title}</h3>
                    <Toggle checked={c.enabled} onChange={(v) => patchChannel(ch, { enabled: v })} label={title} />
                  </div>
                  {c.enabled && (
                    <div className="mt-4 space-y-4">
                      <div>
                        <label htmlFor={`setup-${ch}`} className="block text-[13px] font-semibold text-moca-text mb-1">{fieldLabel}</label>
                        <div className="flex flex-col sm:flex-row gap-2">
                          <input
                            id={`setup-${ch}`}
                            type={type}
                            inputMode={inputMode}
                            dir="ltr"
                            autoComplete={ch === 'email' ? 'email' : 'tel'}
                            value={c[field] || ''}
                            onChange={e => { patchChannel(ch, { [field]: e.target.value }); setTestState(s => ({ ...s, [ch]: undefined })) }}
                            placeholder={placeholder}
                            className="flex-1 min-w-0 rounded-lg border border-moca-border bg-white px-3 py-2 text-[14px] text-moca-text text-start"
                          />
                          <button
                            type="button"
                            disabled={!ok || t === 'sending'}
                            onClick={() => sendTest(ch)}
                            className="px-4 py-2 rounded-lg border border-moca-border text-[13px] font-semibold text-moca-bolt hover:bg-moca-cream disabled:opacity-45 disabled:cursor-not-allowed shrink-0"
                          >
                            {t === 'sending' ? tt('שולח…', 'Sending…') : tt('שליחת הודעת בדיקה', 'Send a test message')}
                          </button>
                        </div>
                        <p role="status" className={`mt-1.5 text-[12.5px] min-h-[18px] ${t === 'sent' ? 'text-moca-down' : 'text-moca-up'}`}>
                          {t === 'sent' && tt('הודעת הבדיקה נשלחה. בדקו שהיא הגיעה.', 'Test message sent. Check that it arrived.')}
                          {t && t !== 'sent' && t !== 'sending' && t}
                        </p>
                      </div>
                      <div>
                        <div className="text-[13px] font-semibold text-moca-text mb-1.5">{tt('תדירות', 'Frequency')}</div>
                        <Seg
                          label={tt('תדירות', 'Frequency') + ' ' + title}
                          value={c.frequency}
                          onChange={(v) => patchChannel(ch, { frequency: v })}
                          options={FREQS.map(f => ({ value: f.v, label: tt(f.he, f.en) }))}
                        />
                        <p className="mt-1.5 text-[12.5px] text-moca-sub">
                          {(() => { const f = FREQS.find(x => x.v === c.frequency); return f ? tt(f.desc.he, f.desc.en) : '' })()}
                        </p>
                      </div>
                    </div>
                  )}
                </section>
              )
            })}
            <p className="text-[12.5px] text-moca-sub">
              {tt('הכתובת והמספר משמשים רק לשליחת ההתראות שהוגדרו כאן. ', 'The address and number are used only to send the alerts set up here. ')}
              <a href="/privacy" target="_blank" rel="noopener" className="underline text-moca-bolt">{tt('מדיניות הפרטיות', 'Privacy policy')}</a>
            </p>
          </>
        )}

        {/* ── 6. Schedule ── */}
        {step.id === 'schedule' && (
          <>
            <Question title={tt('באילו ימים?', 'On which days?')}>
              <div className="flex flex-wrap gap-2">
                {(lang === 'en' ? DAYS_EN : DAYS_HE).map((d, i) => {
                  const on = prefs.quiet.days.includes(i)
                  return (
                    <Chip
                      key={i}
                      pressed={on}
                      onClick={() => {
                        const days = on ? prefs.quiet.days.filter(x => x !== i) : [...prefs.quiet.days, i].sort()
                        if (days.length) patch({ quiet: { ...prefs.quiet, days } })
                      }}
                    >
                      {d}
                    </Chip>
                  )
                })}
              </div>
            </Question>
            <Question
              title={tt('באילו שעות?', 'During which hours?')}
              hint={tt('עדכון שנוצר מחוץ לשעות האלה לא הולך לאיבוד. הוא יישלח בתחילת החלון הבא.', 'An update created outside these hours is not lost. It is sent when the next window opens.')}
            >
              <div className="flex items-center gap-3 flex-wrap">
                <label className="flex items-center gap-2 text-[13.5px] text-moca-text">
                  {tt('מ-', 'From')}
                  <input type="time" dir="ltr" value={prefs.quiet.from} onChange={e => patch({ quiet: { ...prefs.quiet, from: e.target.value || '08:00' } })}
                    className="rounded-lg border border-moca-border bg-white px-2.5 py-1.5 text-[14px]" />
                </label>
                <label className="flex items-center gap-2 text-[13.5px] text-moca-text">
                  {tt('עד', 'To')}
                  <input type="time" dir="ltr" value={prefs.quiet.to} onChange={e => patch({ quiet: { ...prefs.quiet, to: e.target.value || '20:00' } })}
                    className="rounded-lg border border-moca-border bg-white px-2.5 py-1.5 text-[14px]" />
                </label>
              </div>
            </Question>
            <Question title={tt('שפת ההודעות', 'Message language')}>
              <Seg
                label={tt('שפת ההודעות', 'Message language')}
                value={prefs.lang}
                onChange={(v) => patch({ lang: v })}
                options={[{ value: 'he', label: 'עברית' }, { value: 'en', label: 'English' }]}
              />
            </Question>
          </>
        )}

        {/* ── 7. Review ── */}
        {step.id === 'review' && (
          <dl className="divide-y divide-moca-border/50">
            {[
              { id: 'role', k: tt('תפקיד', 'Role'), v: label(ROLES, prefs.role) },
              canEditWs && { id: 'sections', k: tt('במוקד', 'In focus'),
                v: available.filter(s => ws.sections[s.path] === 'focus').map(sectionLabel).join(', ') || tt('לא נבחר', 'None') },
              canEditWs && { id: 'sections', k: tt('מוסתר', 'Hidden'),
                v: available.filter(s => ws.sections[s.path] === 'hidden').map(sectionLabel).join(', ') || tt('שום דבר', 'Nothing') },
              canEditWs && { id: 'sections', k: tt('עמוד פתיחה', 'Landing page'),
                v: (() => { const s = available.find(x => x.path === ws.landing && visiblePaths.includes(x.path)); return s ? sectionLabel(s) : tt('דשבורד', 'Dashboard') })() },
              canEditWs && { id: 'competitors', k: tt('מתחרים במוקד', 'Focus competitors'),
                v: ws.focus_carriers.map(carrierLabel).join(', ') || tt('לא נבחרו', 'None') },
              { id: 'events', k: tt('תחומים', 'Areas'),
                v: shownCategories.filter(c => prefs.categories.includes(c.id)).map(c => tt(c.he, c.en)).join(', ') || tt('לא נבחר', 'None') },
              { id: 'events', k: tt('אירועים', 'Events'),
                v: EVENTS.filter(e => prefs.events.includes(e.id)).map(e => tt(e.he, e.en)).join(', ') || tt('לא נבחר', 'None') },
              { id: 'events', k: tt('סף מחיר', 'Price threshold'), v: label(DELTAS, Number(prefs.min_price_delta)) },
              { id: 'channels', k: tt('מייל', 'E-mail'),
                v: prefs.channels.email.enabled ? `${prefs.channels.email.address} · ${label(FREQS, prefs.channels.email.frequency)}` : tt('כבוי', 'Off'), ltr: prefs.channels.email.enabled },
              { id: 'channels', k: 'WhatsApp',
                v: prefs.channels.whatsapp.enabled ? `${prefs.channels.whatsapp.phone} · ${label(FREQS, prefs.channels.whatsapp.frequency)}` : tt('כבוי', 'Off'), ltr: prefs.channels.whatsapp.enabled },
              { id: 'schedule', k: tt('מתי', 'When'),
                v: `${prefs.quiet.days.map(i => (lang === 'en' ? DAYS_EN : DAYS_HE)[i]).join(' ')} · ${prefs.quiet.from}-${prefs.quiet.to}` },
            ].filter(Boolean).map((row, i) => (
              <div key={i} className="py-2.5 flex items-start gap-3">
                <dt className="w-28 shrink-0 text-[13px] text-moca-sub">{row.k}</dt>
                <dd className="flex-1 min-w-0 text-[14px] text-moca-text break-words">
                  {row.ltr ? <bdi>{row.v}</bdi> : row.v}
                </dd>
                <button type="button" onClick={() => goTo(row.id)} className="text-[12.5px] font-semibold text-moca-bolt underline shrink-0">
                  {tt('עריכה', 'Edit')}
                </button>
              </div>
            ))}
            {!prefs.channels.email.enabled && !prefs.channels.whatsapp.enabled && (
              <p className="pt-3 text-[13px] text-moca-sub">
                {tt('לא נבחר ערוץ התראות, ולכן לא יישלחו הודעות.', 'No alert channel is on, so no messages will be sent.')}
              </p>
            )}
          </dl>
        )}

        {error && <p role="alert" className="mt-4 text-[13.5px] text-moca-up font-semibold">{error}</p>}

        {/* Footer */}
        <div className="mt-7 flex items-center gap-3 flex-wrap">
          {last ? (
            <button type="button" onClick={save} disabled={saving}
              className="px-7 py-2.5 rounded-full bg-moca-bolt text-white text-[14px] font-bold hover:opacity-90 disabled:opacity-60">
              {saving ? tt('שומר…', 'Saving…') : tt('שמירה וסיום', 'Save and finish')}
            </button>
          ) : (
            <button type="button" onClick={goNext}
              className="px-7 py-2.5 rounded-full bg-moca-bolt text-white text-[14px] font-bold hover:opacity-90">
              {tt('המשך', 'Continue')}
            </button>
          )}
          {stepIdx > 0 && (
            <button type="button" onClick={goBack} className="px-5 py-2.5 rounded-full border border-moca-border text-[14px] text-moca-text hover:bg-moca-cream">
              {tt('חזרה', 'Back')}
            </button>
          )}
          {welcome && (
            <button type="button" onClick={skip} className="ms-auto text-[13px] text-moca-sub underline hover:text-moca-text">
              {tt('דילוג, אגדיר אחר כך', 'Skip, I will set this up later')}
            </button>
          )}
        </div>
      </div>

      {/* Reset - only when something was saved before */}
      {(hasUserSetup || hasWsSetup) && (
        <section aria-label={tt('איפוס', 'Reset')} className="mt-6 rounded-2xl border border-moca-border/60 bg-white p-5 md:px-7">
          <h2 className="text-[15px] font-bold text-moca-text mb-1">{tt('איפוס', 'Reset')}</h2>
          <ul className="divide-y divide-moca-border/50">
            {[
              hasUserSetup && {
                kind: 'user',
                title: tt('איפוס ההתראות שלי', 'Reset my alerts'),
                desc: tt('מוחק את הערוצים, הכתובת, מספר הטלפון וכל שאר הבחירות האישיות. לא יישלחו עוד התראות.',
                         'Deletes your channels, address, phone number and every other personal choice. No more alerts are sent.'),
              },
              hasWsSetup && {
                kind: 'workspace',
                title: tt('איפוס תצוגת הארגון', 'Reset the organization view'),
                desc: tt('מחזיר את התפריט, עמוד הפתיחה והמתחרים במוקד לברירת המחדל, לכל המשתמשים בארגון. ההתראות האישיות של המשתמשים לא משתנות.',
                         'Returns the menu, landing page and focus competitors to the default for everyone in your organization. Members\' personal alerts are not changed.'),
              },
            ].filter(Boolean).map(row => (
              <li key={row.kind} className="py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-semibold text-moca-text">{row.title}</div>
                  <div className="text-[12.5px] text-moca-sub">{row.desc}</div>
                </div>
                {confirmReset === row.kind ? (
                  <div className="flex items-center gap-2 shrink-0">
                    <button type="button" onClick={() => doReset(row.kind)} disabled={resetting}
                      className="px-4 py-2 rounded-full bg-moca-up text-white text-[13px] font-bold hover:opacity-90 disabled:opacity-60">
                      {resetting ? tt('מאפס…', 'Resetting…') : tt('כן, לאפס', 'Yes, reset')}
                    </button>
                    <button type="button" onClick={() => setConfirmReset(null)} disabled={resetting}
                      className="px-4 py-2 rounded-full border border-moca-border text-[13px] text-moca-text hover:bg-moca-cream">
                      {tt('ביטול', 'Cancel')}
                    </button>
                  </div>
                ) : (
                  <button type="button" onClick={() => { setResetMsg(null); setConfirmReset(row.kind) }}
                    className="self-start sm:self-auto px-4 py-2 rounded-full border border-moca-up/50 text-[13px] font-semibold text-moca-up hover:bg-moca-cream shrink-0">
                    {tt('איפוס', 'Reset')}
                  </button>
                )}
              </li>
            ))}
          </ul>
          <p role="status" className={`text-[13px] min-h-[20px] ${resetMsg?.ok === false ? 'text-moca-up' : 'text-moca-down'}`}>
            {resetMsg?.text}
          </p>
        </section>
      )}
      {/* The confirmation of the LAST reset must stay visible after the section above disappears */}
      {!(hasUserSetup || hasWsSetup) && resetMsg && (
        <p role="status" className={`mt-4 text-[13px] ${resetMsg.ok === false ? 'text-moca-up' : 'text-moca-down'}`}>{resetMsg.text}</p>
      )}
    </div>
  )
}
