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
  '/executive-summary', '/positioning', '/compare', '/ai-insights',
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
