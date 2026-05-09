import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import { useWatchlist } from '../../hooks/useWatchlist'
import Logo from '../Logo'

/**
 * Right-side sidebar (RTL start) — primary navigation per MOCA design handoff.
 * Groups: ניטור / תובנות / מסלולים / כלים. Routes that live as tabs on the
 * dashboard (?tab=history, ?tab=banners, ?tab=abroad, ?tab=global) are
 * deep-linked rather than full pages.
 */

const FLAG_FOR_PATH = {
  '/compare':           'hide_compare',
  '/positioning':       'hide_positioning',
  '/alerts':            'hide_alerts',
  '/executive-summary': 'hide_executive_summary',
  '/archive':           'hide_archive',
  '/ai-insights':       'hide_ai_insights',
}

// Lucide-style inline SVGs — render reliably in RTL/BiDi (Unicode glyphs
// occasionally flip or render with the wrong baseline in mixed contexts).
const ICON_PROPS = {
  width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', strokeWidth: 2,
  strokeLinecap: 'round', strokeLinejoin: 'round',
  'aria-hidden': true,
}

const Icons = {
  dashboard: (
    <svg {...ICON_PROPS}><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>
  ),
  exec: (
    <svg {...ICON_PROPS}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="14 3 14 9 20 9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>
  ),
  positioning: (
    <svg {...ICON_PROPS}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>
  ),
  history: (
    <svg {...ICON_PROPS}><path d="M3 12a9 9 0 1 0 3-6.7"/><polyline points="3 4 3 10 9 10"/><polyline points="12 7 12 12 15 14"/></svg>
  ),
  alerts: (
    <svg {...ICON_PROPS}><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
  ),
  ai: (
    <svg {...ICON_PROPS}><path d="M12 3v2M12 19v2M5 12H3M21 12h-2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/><circle cx="12" cy="12" r="4"/></svg>
  ),
  banners: (
    <svg {...ICON_PROPS}><rect x="3" y="3" width="18" height="14" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m21 14-5-5L5 20"/></svg>
  ),
  archive: (
    <svg {...ICON_PROPS}><rect x="3" y="3" width="18" height="5" rx="1"/><path d="M5 8v11a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><line x1="10" y1="13" x2="14" y2="13"/></svg>
  ),
  plans: (
    <svg {...ICON_PROPS}><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="14" y2="18"/></svg>
  ),
  roaming: (
    <svg {...ICON_PROPS}><circle cx="12" cy="12" r="9"/><line x1="3" y1="12" x2="21" y2="12"/><path d="M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>
  ),
  esim: (
    <svg {...ICON_PROPS}><rect x="5" y="3" width="14" height="18" rx="2"/><line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="13" y2="11"/><circle cx="12" cy="17" r="1.5"/></svg>
  ),
  search: (
    <svg {...ICON_PROPS}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
  ),
  workspace: (
    <svg {...ICON_PROPS}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V10a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
  ),
}

function NavItem({ to, icon, label, badge, badgeColor, end, onClick, isActive }) {
  // We support both internal route navigation (NavLink) and pure-button items
  // (e.g. search opens a Cmd+K modal). When `onClick` is provided and `to` is
  // null, we render a button.
  const inner = (active) => (
    <span
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 12px',
        borderRadius: 10,
        background: active ? 'var(--color-moca-bolt)' : 'transparent',
        color: active ? '#fff' : 'var(--color-moca-text)',
        fontSize: 13.5,
        fontWeight: active ? 700 : 500,
        transition: 'background 120ms ease, color 120ms ease',
        cursor: 'pointer',
        position: 'relative',
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 20,
          height: 16,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: active ? 1 : 0.78,
          color: active ? '#fff' : 'var(--color-moca-sub)',
          flexShrink: 0,
        }}
      >
        {icon}
      </span>
      <span style={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {label}
      </span>
      {badge != null && badge !== 0 && (
        <span
          className="tnum"
          style={{
            fontSize: 10,
            padding: '1px 6px',
            borderRadius: 999,
            fontWeight: 800,
            background: active ? 'rgba(255,255,255,0.18)' : (badgeColor || 'var(--color-moca-cream)'),
            color: active ? '#fff' : 'var(--color-moca-bolt)',
            flexShrink: 0,
          }}
        >
          {badge}
        </span>
      )}
    </span>
  )

  if (!to && onClick) {
    return (
      <button
        onClick={onClick}
        style={{
          background: 'transparent',
          border: 'none',
          padding: 0,
          margin: 0,
          width: '100%',
          textAlign: 'inherit',
          font: 'inherit',
          cursor: 'pointer',
        }}
      >
        {inner(false)}
      </button>
    )
  }

  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      {({ isActive: linkActive }) => inner(isActive ?? linkActive)}
    </NavLink>
  )
}

function GroupLabel({ children }) {
  return (
    <div
      style={{
        fontSize: 10,
        color: 'var(--color-moca-muted)',
        fontWeight: 800,
        letterSpacing: 0.8,
        textTransform: 'uppercase',
        padding: '14px 14px 6px',
      }}
    >
      {children}
    </div>
  )
}

export default function Sidebar({ className = '' }) {
  const { isAdmin, isSuperAdmin, workspace } = useAuth()
  const flags = useFeatureFlags()
  const { changesCount } = useWatchlist()
  const location = useLocation()

  const visible = (path) => !FLAG_FOR_PATH[path] || !flags[FLAG_FOR_PATH[path]]
  const appTitle = workspace?.brand_config?.app_title || null
  const logoUrl  = workspace?.brand_config?.logo_url  || null

  // Custom active-detection for tab-suffixed routes — NavLink's default
  // `end` matching doesn't account for `?tab=X` query strings.
  const isPath = (path, tab) => {
    if (tab) {
      const currentTab = new URLSearchParams(location.search).get('tab')
      return location.pathname === '/' && currentTab === tab
    }
    if (path === '/') {
      const currentTab = new URLSearchParams(location.search).get('tab')
      return location.pathname === '/' && (!currentTab || currentTab === 'domestic')
    }
    return location.pathname === path || location.pathname.startsWith(path + '/')
  }

  const openSearch = () => {
    // GlobalSearch listens for Ctrl/Cmd+K — synthesize the same event.
    window.dispatchEvent(new KeyboardEvent('keydown', {
      ctrlKey: true,
      code: 'KeyK',
      key: 'k',
      bubbles: true,
    }))
  }

  return (
    <aside
      className={`hidden md:flex md:flex-col ${className}`}
      style={{
        position: 'sticky',
        top: 0,
        alignSelf: 'flex-start',
        height: '100vh',
        width: 240,
        flexShrink: 0,
        background: 'var(--color-moca-cream)',
        borderInlineStart: '1px solid var(--color-moca-border)',
        overflowY: 'auto',
        zIndex: 30,
      }}
    >
      {/* Logo block */}
      <div style={{ padding: '18px 14px 8px' }}>
        <NavLink to="/" style={{ textDecoration: 'none' }}>
          <Logo size="md" appTitle={appTitle} logoUrl={logoUrl} />
        </NavLink>
      </div>

      <nav style={{ padding: '8px 8px 16px', display: 'flex', flexDirection: 'column', gap: 1 }}>
        {/* ─── ניטור ─── */}
        <GroupLabel>ניטור</GroupLabel>
        <NavItem to="/" end icon={Icons.dashboard} label="דשבורד" isActive={isPath('/')} />
        {visible('/executive-summary') && (
          <NavItem to="/executive-summary" icon={Icons.exec} label="דוח מנהלים" isActive={isPath('/executive-summary')} />
        )}
        {visible('/positioning') && (
          <NavItem to="/positioning" icon={Icons.positioning} label="מיצוב תחרותי" isActive={isPath('/positioning')} />
        )}
        <NavItem to="/?tab=history" icon={Icons.history} label="היסטוריית שינויים" isActive={isPath(null, 'history')} />
        {visible('/alerts') && (
          <NavItem
            to="/alerts"
            icon={Icons.alerts}
            label="התראות"
            badge={changesCount > 0 ? (changesCount > 99 ? '99+' : changesCount) : null}
            badgeColor="var(--color-moca-up)"
            isActive={isPath('/alerts')}
          />
        )}

        {/* ─── תובנות ─── */}
        <GroupLabel>תובנות</GroupLabel>
        {visible('/ai-insights') && (
          <NavItem to="/ai-insights" icon={Icons.ai} label="AI Insights" isActive={isPath('/ai-insights')} />
        )}
        <NavItem to="/?tab=banners" icon={Icons.banners} label="באנרים" isActive={isPath(null, 'banners')} />
        {visible('/archive') && (
          <NavItem to="/archive" icon={Icons.archive} label="ארכיב Snapshots" isActive={isPath('/archive')} />
        )}

        {/* ─── מסלולים ─── */}
        <GroupLabel>מסלולים</GroupLabel>
        {visible('/compare') && (
          <NavItem to="/compare" icon={Icons.plans} label="השוואת מסלולים" isActive={isPath('/compare')} />
        )}
        <NavItem to="/?tab=abroad" icon={Icons.roaming} label={'חו״ל · Roaming'} isActive={isPath(null, 'abroad')} />
        <NavItem to="/?tab=global" icon={Icons.esim} label="eSIM גלובלי" isActive={isPath(null, 'global')} />

        {/* ─── כלים ─── */}
        <GroupLabel>כלים</GroupLabel>
        <NavItem
          icon={Icons.search}
          label={<span>חיפוש מתקדם <kbd style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'var(--color-moca-sand)', color: 'var(--color-moca-sub)', marginInlineStart: 6, fontFamily: 'inherit' }}>Ctrl K</kbd></span>}
          onClick={openSearch}
        />
        {(isAdmin || isSuperAdmin) && (
          <NavItem
            to={isSuperAdmin ? '/admin/workspaces' : '/workspace/users'}
            icon={Icons.workspace}
            label="Workspace"
            isActive={location.pathname.startsWith('/workspace') || location.pathname.startsWith('/admin')}
          />
        )}
      </nav>
    </aside>
  )
}
