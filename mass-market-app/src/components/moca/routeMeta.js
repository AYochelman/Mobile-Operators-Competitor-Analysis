/**
 * Route → page metadata used by <Topbar>.
 *
 * Keys are matched in order: exact match wins; `/path/*` wildcards match
 * any descendant; `*` is a fallback. Tab-suffix entries (`/?tab=banners`)
 * are checked against the full pathname + search.
 */

export const ROUTE_META = [
  { match: '/',                kicker: 'ניטור',     title: 'דשבורד' },
  { match: '/plans',           kicker: 'מסלולים',   title: 'השוואת מסלולים' },
  { match: '/roaming',         kicker: 'מסלולים',   title: 'חו״ל · Roaming' },
  { match: '/esim',            kicker: 'מסלולים',   title: 'eSIM גלובלי' },
  { match: '/resellers',       kicker: 'מסלולים',   title: 'משווקים' },
  { match: '/content',         kicker: 'מסלולים',   title: 'שירותי תוכן' },
  { match: '/news',            kicker: 'תובנות',    title: 'בחדשות' },
  { match: '/banners',         kicker: 'תובנות',    title: 'באנרים פעילים' },
  { match: '/history',         kicker: 'ניטור',     title: 'היסטוריית שינויים' },
  { match: '/compare',         kicker: 'מסלולים',   title: 'השוואת מחירים · גרפים' },
  { match: '/positioning',     kicker: 'ניטור',     title: 'מיצוב תחרותי' },
  { match: '/alerts',          kicker: 'ניטור',     title: 'התראות' },
  { match: '/executive-summary', kicker: 'ניטור',   title: 'דוח מנהלים שבועי' },
  { match: '/ai-insights',     kicker: 'תובנות',    title: 'AI Insights' },
  { match: '/archive',         kicker: 'תובנות',    title: 'ארכיב Snapshots' },
  { match: '/preferences',     kicker: 'כלים',      title: 'העדפות' },
  { match: '/notifications',   kicker: 'כלים',      title: 'הגדרות התראות' },
  { match: '/settings',        kicker: 'ניהול',     title: 'הגדרות מערכת' },
  { match: '/workspace/users', kicker: 'ניהול',     title: 'הצוות' },
  { match: '/workspace/settings', kicker: 'ניהול',  title: 'מיתוג Workspace' },
  { match: '/admin/workspaces', kicker: 'ניהול',    title: 'Workspaces' },
  { match: '/admin/audit',     kicker: 'ניהול',     title: 'יומן ביקורת' },
]

export function resolveRouteMeta(pathname /*, search */) {
  for (const r of ROUTE_META) {
    if (r.match === pathname) return r
  }
  return { kicker: '', title: 'MOCA' }
}
