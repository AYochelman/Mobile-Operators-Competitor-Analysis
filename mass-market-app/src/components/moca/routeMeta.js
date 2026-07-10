/**
 * Route → page metadata used by <Topbar>.
 *
 * Keys are matched in order: exact match wins; `/path/*` wildcards match
 * any descendant; `*` is a fallback. Tab-suffix entries (`/?tab=banners`)
 * are checked against the full pathname + search.
 *
 * Each kicker/title carries both languages; resolveRouteMeta(pathname, search,
 * lang) returns the strings for the active UI language.
 */

export const ROUTE_META = [
  { match: '/',                  kicker: { he: 'ניטור',        en: 'Monitoring' },    title: { he: 'דשבורד',              en: 'Dashboard' } },
  { match: '/plans',             kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'השוואת מסלולים',       en: 'Plan comparison' } },
  { match: '/roaming',           kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'חו״ל · Roaming',       en: 'Roaming' } },
  { match: '/esim',              kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'eSIM גלובלי',          en: 'Global eSIM' } },
  { match: '/esim-banners',      kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'באנרים גלובליים',      en: 'Global banners' } },
  { match: '/usa',               kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'נוחתים בארה״ב',        en: 'Landing in the USA' } },
  { match: '/resellers',         kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'משווקים',              en: 'Resellers' } },
  { match: '/content',           kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'שירותי תוכן',          en: 'Content services' } },
  { match: '/news',              kicker: { he: 'תובנות',       en: 'Insights' },      title: { he: 'בחדשות',               en: 'In the news' } },
  { match: '/social',            kicker: { he: 'תובנות',       en: 'Insights' },      title: { he: 'ברשתות החברתיות',      en: 'On social media' } },
  { match: '/banners',           kicker: { he: 'תובנות',       en: 'Insights' },      title: { he: 'באנרים פעילים',        en: 'Active banners' } },
  { match: '/history',           kicker: { he: 'ניטור',        en: 'Monitoring' },    title: { he: 'היסטוריית שינויים',    en: 'Change history' } },
  { match: '/compare',           kicker: { he: 'מסלולים',      en: 'Plans' },         title: { he: 'השוואת מחירים · גרפים', en: 'Price comparison · Charts' } },
  { match: '/positioning',       kicker: { he: 'ניטור',        en: 'Monitoring' },    title: { he: 'מיצוב תחרותי',         en: 'Competitive positioning' } },
  { match: '/alerts',            kicker: { he: 'ניטור',        en: 'Monitoring' },    title: { he: 'התראות',               en: 'Alerts' } },
  { match: '/executive-summary', kicker: { he: 'ניטור',        en: 'Monitoring' },    title: { he: 'דוח מנהלים שבועי',     en: 'Weekly executive report' } },
  { match: '/ai-insights',       kicker: { he: 'תובנות',       en: 'Insights' },      title: { he: 'AI Insights',          en: 'AI Insights' } },
  { match: '/archive',           kicker: { he: 'תובנות',       en: 'Insights' },      title: { he: 'מכונת זמן',            en: 'Time Machine' } },
  { match: '/preferences',       kicker: { he: 'כלים',         en: 'Tools' },         title: { he: 'העדפות',               en: 'Preferences' } },
  { match: '/notifications',     kicker: { he: 'כלים',         en: 'Tools' },         title: { he: 'הגדרות התראות',        en: 'Notification settings' } },
  { match: '/settings',          kicker: { he: 'ניהול',        en: 'Admin' },         title: { he: 'הגדרות מערכת',         en: 'System settings' } },
  { match: '/workspace/users',   kicker: { he: 'ניהול',        en: 'Admin' },         title: { he: 'הצוות',                en: 'Team' } },
  { match: '/workspace/settings',kicker: { he: 'ניהול',        en: 'Admin' },         title: { he: 'מיתוג Workspace',      en: 'Workspace branding' } },
  { match: '/admin/workspaces',  kicker: { he: 'ניהול',        en: 'Admin' },         title: { he: 'Workspaces',           en: 'Workspaces' } },
  { match: '/admin/audit',       kicker: { he: 'ניהול',        en: 'Admin' },         title: { he: 'יומן ביקורת',          en: 'Audit log' } },
  { match: '/usage',             kicker: { he: 'ניהול',        en: 'Admin' },         title: { he: 'שימוש ב-Claude API',   en: 'Claude API usage' } },
  { match: '/admin/user-activity',kicker: { he: 'ניהול',       en: 'Admin' },         title: { he: 'פעילות משתמשים',       en: 'User activity' } },
  { match: '/admin/hotels',      kicker: { he: 'Guest Connect',en: 'Guest Connect' }, title: { he: 'פורטלי אורחים',        en: 'Guest portals' } },
  { match: '/admin/esim',        kicker: { he: 'B2C',          en: 'B2C' },           title: { he: 'דשבורד eSIM',          en: 'eSIM dashboard' } },
  { match: '/admin/deals',       kicker: { he: 'B2C',          en: 'B2C' },           title: { he: 'סטטוס ספקים',          en: 'Provider status' } },
]

function pick(val, lang) {
  if (val == null) return ''
  if (typeof val === 'string') return val
  return val[lang] != null ? val[lang] : (val.he != null ? val.he : '')
}

export function resolveRouteMeta(pathname, _search, lang = 'he') {
  for (const r of ROUTE_META) {
    if (r.match === pathname) {
      return { kicker: pick(r.kicker, lang), title: pick(r.title, lang) }
    }
  }
  return { kicker: '', title: 'MOCA' }
}
