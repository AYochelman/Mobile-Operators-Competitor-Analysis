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

// Inline glyphs — match the design's information-architecture symbols.
// Switch to a proper icon set (Lucide/Phosphor) in a later phase.
const GLYPH = {
  dashboard:   '◉',
  exec:        '▤',
  positioning: '◎',
  history:     '◈',
  alerts:      '!',
  ai:          '✦',
  banners:     '▥',
  archive:     '⧉',
  plans:       '▢',
  roaming:     '◇',
  esim:        '◌',
  search:      '⌕',
  workspace:   '⚙',
}

function NavItem({ to, glyph, label, badge, badgeColor, end, onClick, isActive }) {
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
          textAlign: 'center',
          fontSize: 15,
          opacity: active ? 1 : 0.7,
          color: active ? '#fff' : 'var(--color-moca-sub)',
          flexShrink: 0,
        }}
      >
        {glyph}
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
        <NavItem to="/" end glyph={GLYPH.dashboard} label="דשבורד" isActive={isPath('/')} />
        {visible('/executive-summary') && (
          <NavItem to="/executive-summary" glyph={GLYPH.exec} label="דוח מנהלים" isActive={isPath('/executive-summary')} />
        )}
        {visible('/positioning') && (
          <NavItem to="/positioning" glyph={GLYPH.positioning} label="מיצוב תחרותי" isActive={isPath('/positioning')} />
        )}
        <NavItem to="/?tab=history" glyph={GLYPH.history} label="היסטוריית שינויים" isActive={isPath(null, 'history')} />
        {visible('/alerts') && (
          <NavItem
            to="/alerts"
            glyph={GLYPH.alerts}
            label="התראות"
            badge={changesCount > 0 ? (changesCount > 99 ? '99+' : changesCount) : null}
            badgeColor="var(--color-moca-up)"
            isActive={isPath('/alerts')}
          />
        )}

        {/* ─── תובנות ─── */}
        <GroupLabel>תובנות</GroupLabel>
        {visible('/ai-insights') && (
          <NavItem to="/ai-insights" glyph={GLYPH.ai} label="AI Insights" isActive={isPath('/ai-insights')} />
        )}
        <NavItem to="/?tab=banners" glyph={GLYPH.banners} label="באנרים" isActive={isPath(null, 'banners')} />
        {visible('/archive') && (
          <NavItem to="/archive" glyph={GLYPH.archive} label="ארכיב Snapshots" isActive={isPath('/archive')} />
        )}

        {/* ─── מסלולים ─── */}
        <GroupLabel>מסלולים</GroupLabel>
        {visible('/compare') && (
          <NavItem to="/compare" glyph={GLYPH.plans} label="השוואת מסלולים" isActive={isPath('/compare')} />
        )}
        <NavItem to="/?tab=abroad" glyph={GLYPH.roaming} label={'חו״ל · Roaming'} isActive={isPath(null, 'abroad')} />
        <NavItem to="/?tab=global" glyph={GLYPH.esim} label="eSIM גלובלי" isActive={isPath(null, 'global')} />

        {/* ─── כלים ─── */}
        <GroupLabel>כלים</GroupLabel>
        <NavItem
          glyph={GLYPH.search}
          label={<span>חיפוש מתקדם <kbd style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'var(--color-moca-sand)', color: 'var(--color-moca-sub)', marginInlineStart: 6, fontFamily: 'inherit' }}>Ctrl K</kbd></span>}
          onClick={openSearch}
        />
        {(isAdmin || isSuperAdmin) && (
          <NavItem
            to={isSuperAdmin ? '/admin/workspaces' : '/workspace/users'}
            glyph={GLYPH.workspace}
            label="Workspace"
            isActive={location.pathname.startsWith('/workspace') || location.pathname.startsWith('/admin')}
          />
        )}
      </nav>
    </aside>
  )
}
