// Single source of truth: nav path → feature-flag key that hides it.
// Consumed by Sidebar.jsx + Navbar.jsx (nav-item visibility) and mirrored by
// FLAG_DEFINITIONS in WorkspacesAdminPage.jsx (the admin checkboxes). Keep the
// three in sync — a flag the admin panel offers but no nav consults is a
// checkbox that hides nothing (this is exactly the drift that broke workspace
// hiding: the admin panel offered hide_abroad/global/content/banners/history/
// news, but the sidebar never mapped those paths).
//
// The DashboardPage in-page tab bar hides tabs generically via
// flags['hide_' + tab.id] (ids: domestic/abroad/global/usa/resellers/content/
// banners/history/news), so those keys line up with the tab ids by design.
export const FLAG_FOR_PATH = {
  // בית
  '/':                  'hide_dashboard',
  // מסלולים
  '/plans':             'hide_domestic',
  '/roaming':           'hide_abroad',
  '/esim':              'hide_global',
  '/esim-banners':      'hide_global_banners',
  '/usa':               'hide_usa',
  '/resellers':         'hide_resellers',
  '/content':           'hide_content',
  '/compare':           'hide_compare',
  // תובנות
  '/cockpit':           'hide_cockpit',
  '/agent-desk':        'hide_agent_desk',
  '/executive-summary': 'hide_executive_summary',
  '/positioning':       'hide_positioning',
  '/ai-insights':       'hide_ai_insights',
  '/news':              'hide_news',
  '/social':            'hide_social',
  '/banners':           'hide_banners',
  '/archive':           'hide_archive',
  // ניטור
  '/history':           'hide_history',
  '/alerts':            'hide_alerts',
}

// When the dashboard home ("/") is hidden, land the user on the first visible
// primary section instead (priority order). '/preferences' is always available
// (no flag) so this never returns nothing / loops.
const HOME_FALLBACK_ORDER = [
  '/plans', '/roaming', '/esim', '/esim-banners', '/usa', '/resellers', '/content',
  '/cockpit', '/agent-desk', '/executive-summary', '/positioning', '/compare', '/ai-insights',
  '/news', '/social', '/banners', '/archive', '/history', '/alerts',
]

export function firstVisibleHome(flags = {}) {
  for (const path of HOME_FALLBACK_ORDER) {
    if (!flags[FLAG_FOR_PATH[path]]) return path
  }
  return '/preferences'
}

// ─── Display-mode presets ─────────────────────────────────────────────────
// One-click macros over feature_flags so an admin doesn't hand-tick 15+ boxes.
// A preset only ever writes the "section" flags below — it never touches other
// flags (e.g. hide_chat), so those survive a preset switch. `hide_chat` is a
// feature toggle, not a nav section, so it's deliberately excluded.
export const SECTION_FLAGS = Object.values(FLAG_FOR_PATH)

// `only` = the single section flag to LEAVE OFF (that section stays visible);
// every other section is hidden. `only: null` = show everything.
export const DISPLAY_PRESETS = [
  { id: 'all',       label: 'הכל (ברירת מחדל)', only: null },
  { id: 'domestic',  label: 'סלולר בלבד',        only: 'hide_domestic' },
  { id: 'roaming',   label: 'חו״ל בלבד',         only: 'hide_abroad' },
  { id: 'global',    label: 'גלובלי בלבד',       only: 'hide_global' },
  { id: 'usa',       label: 'ארה״ב בלבד',        only: 'hide_usa' },
  { id: 'resellers', label: 'משווקים בלבד',      only: 'hide_resellers' },
  { id: 'content',   label: 'תוכן בלבד',         only: 'hide_content' },
]

// Returns a NEW feature_flags object with the preset applied (section flags
// rewritten, all other flags preserved). 'custom' is a no-op sentinel.
export function applyDisplayPreset(currentFlags, presetId) {
  const next = { ...(currentFlags || {}) }
  if (presetId === 'custom') return next
  SECTION_FLAGS.forEach(f => { delete next[f] })              // reset sections → visible
  const preset = DISPLAY_PRESETS.find(p => p.id === presetId)
  if (preset && preset.only) {
    SECTION_FLAGS.forEach(f => { if (f !== preset.only) next[f] = true })
  }
  return next
}

// Which preset (if any) the current flags match — else 'custom'. Only the
// section flags are compared, so hide_chat etc. don't force 'custom'.
export function detectDisplayPreset(flags = {}) {
  const active = new Set(SECTION_FLAGS.filter(f => flags[f]))
  if (active.size === 0) return 'all'
  for (const p of DISPLAY_PRESETS) {
    if (!p.only) continue
    const expected = SECTION_FLAGS.filter(f => f !== p.only)
    if (active.size === expected.length && expected.every(f => active.has(f))) return p.id
  }
  return 'custom'
}

// ─── Section catalog + the /setup wizard's workspace answers ───────────────
// One list of every hideable nav section: the Sidebar renders from it and the
// dashboard-setup wizard (pages/SetupWizardPage.jsx) offers the same rows, so a
// section can never exist in one and not the other. `desc` is the wizard's
// one-line explanation. Mirror on the server: SECTION_FLAGS in dashboard_setup.py.
export const NAV_GROUPS = [
  { key: 'monitoring', he: 'ניטור',   en: 'Monitoring' },
  { key: 'insights',   he: 'תובנות',  en: 'Insights' },
  { key: 'plans',      he: 'מסלולים', en: 'Plans' },
]

export const NAV_SECTIONS = [
  { path: '/',                  group: 'monitoring', he: 'דשבורד',             en: 'Dashboard',
    desc: { he: 'תמונת מצב יומית של השוק והמתחרים', en: 'Daily snapshot of the market and competitors' } },
  { path: '/cockpit',           group: 'monitoring', he: 'חדר מצב',            en: 'Situation room',
    desc: { he: 'מסך אחד להנהלה: מחיר, נפח ושינויי השבוע', en: 'One executive screen: price, volume, weekly changes' } },
  { path: '/agent-desk',        group: 'monitoring', he: 'עמדת נציג',          en: 'Agent desk',
    desc: { he: 'מענה מהיר לנציג מול לקוח שמצטט מתחרה', en: 'Fast answers for a rep facing a competitor quote' } },
  { path: '/executive-summary', group: 'monitoring', he: 'דוח מנהלים',         en: 'Executive report',
    desc: { he: 'סיכום שוק מוכן להצגה, כולל ניתוח AI', en: 'Presentation-ready market summary with AI analysis' } },
  { path: '/positioning',       group: 'monitoring', he: 'מיצוב תחרותי',       en: 'Positioning',
    desc: { he: 'איפה כל מפעיל עומד ביחס מחיר ונפח', en: 'Where each carrier stands on price and volume' } },
  { path: '/history',           group: 'monitoring', he: 'היסטוריית שינויים',  en: 'Change history',
    desc: { he: 'כל שינוי מחיר, השקה והסרה לאורך זמן', en: 'Every price move, launch and removal over time' } },
  { path: '/alerts',            group: 'monitoring', he: 'התראות',             en: 'Alerts',
    desc: { he: 'התראות מחיר אישיות ורשימת מעקב', en: 'Personal price alerts and watchlist' } },

  { path: '/ai-insights',       group: 'insights',   he: 'AI Insights',        en: 'AI Insights',
    desc: { he: 'תובנות AI על כל מתחרה', en: 'AI insights on each competitor' } },
  { path: '/news',              group: 'insights',   he: 'בחדשות',             en: 'In the news',
    desc: { he: 'כתבות על המפעילים בתקשורת', en: 'Press coverage of the carriers' } },
  { path: '/social',            group: 'insights',   he: 'ברשתות החברתיות',    en: 'On social',
    desc: { he: 'מה נאמר על המפעילים ברשתות', en: 'What is being said about the carriers' } },
  { path: '/banners',           group: 'insights',   he: 'באנרים',             en: 'Banners',
    desc: { he: 'צילומי עמודי הבית והחנויות של המתחרים', en: 'Screenshots of competitor homepages and stores' } },
  { path: '/archive',           group: 'insights',   he: 'מכונת זמן',          en: 'Time Machine',
    desc: { he: 'איך נראה השוק בכל תאריך בעבר', en: 'What the market looked like on any past date' } },

  { path: '/plans',             group: 'plans',      he: 'Mass Market',        en: 'Mass Market',
    wizard: { he: 'חבילות סלולר (Mass Market)', en: 'Mobile plans (Mass Market)' },
    desc: { he: 'כל חבילות הסלולר של המפעילים בישראל', en: 'Every mobile plan of the Israeli carriers' } },
  { path: '/roaming',           group: 'plans',      he: 'חו״ל · Roaming',     en: 'Roaming',
    desc: { he: 'חבילות חו״ל של המפעילים, לפי מדינה', en: 'Carrier roaming packages by country' } },
  { path: '/esim',              group: 'plans',      he: 'eSIM גלובלי',        en: 'Global eSIM',
    desc: { he: 'ספקי eSIM בינלאומיים, לפי יעד', en: 'International eSIM providers by destination' } },
  { path: '/esim-banners',      group: 'plans',      he: 'באנרים גלובליים',    en: 'Global banners',
    desc: { he: 'צילומי עמודי הבית של ספקי ה-eSIM', en: 'Screenshots of eSIM provider homepages' } },
  { path: '/usa',               group: 'plans',      he: 'נוחתים בארה״ב',      en: 'USA',
    desc: { he: 'חבילות פריפייד אמריקאיות לתיירים', en: 'US prepaid plans for tourists' } },
  { path: '/resellers',         group: 'plans',      he: 'משווקים',            en: 'Resellers',
    desc: { he: 'מבצעים מתחת לקו: משווקים, דפי נחיתה ופייסבוק', en: 'Below-the-line offers: resellers, landing pages, Facebook' } },
  { path: '/content',           group: 'plans',      he: 'תוכן',               en: 'Content',
    desc: { he: 'שירותי ערך מוסף: סייבר, שעון, תא קולי ועוד', en: 'Value-added services: cyber, watch, voicemail and more' } },
  { path: '/compare',           group: 'plans',      he: 'השוואת מחירים',      en: 'Price compare',
    desc: { he: 'גרפים להשוואת מחירים בין מפעילים', en: 'Charts comparing prices across carriers' } },
]

// Flags hidden by the customer's OWN admin in the wizard (workspace.dashboard_config),
// as opposed to workspace.feature_flags which only the operator sets.
export function wizardHiddenFlags(dashboardConfig) {
  const sections = dashboardConfig?.sections || {}
  const out = {}
  for (const [path, state] of Object.entries(sections)) {
    if (state === 'hidden' && FLAG_FOR_PATH[path]) out[FLAG_FOR_PATH[path]] = true
  }
  return out
}

// feature_flags ∪ wizard-hidden sections = what the nav actually hides.
export function effectiveFlags(workspace) {
  return { ...(workspace?.feature_flags || {}), ...wizardHiddenFlags(workspace?.dashboard_config) }
}

// Paths the admin marked "במוקד" - pinned to the top of the nav, in catalog order.
export function focusPaths(workspace, flags = {}) {
  const sections = workspace?.dashboard_config?.sections || {}
  return NAV_SECTIONS
    .map(s => s.path)
    .filter(p => sections[p] === 'focus' && !flags[FLAG_FOR_PATH[p]])
}

// The landing page chosen in the wizard, when it is still visible.
export function landingPath(workspace, flags = {}) {
  const landing = workspace?.dashboard_config?.landing
  if (!landing || !(landing in FLAG_FOR_PATH) || flags[FLAG_FOR_PATH[landing]]) return null
  return landing
}
