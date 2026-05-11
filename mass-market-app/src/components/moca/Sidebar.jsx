import { useEffect } from 'react'
import { createPortal } from 'react-dom'
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
  resellers: (
    <svg {...ICON_PROPS}><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
  ),
  content: (
    <svg {...ICON_PROPS}><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><path d="M7 8l2 2-2 2M11 12h6"/></svg>
  ),
  search: (
    <svg {...ICON_PROPS}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
  ),
  workspace: (
    <svg {...ICON_PROPS}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V10a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
  ),
}

function NavItem({ to, icon, label, badge, badgeColor, end, onClick, isActive, onAfterNav }) {
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
        onClick={() => { onClick(); onAfterNav && onAfterNav() }}
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
      onClick={() => { onClick && onClick(); onAfterNav && onAfterNav() }}
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

/**
 * Universal sidebar — same content on desktop (always-visible aside) and
 * mobile (slide-in drawer triggered by the hamburger button).
 *
 * Desktop:  <Sidebar />               — sticky right column, hidden <md
 * Mobile:   <Sidebar mobile open onClose={...} /> — portal drawer
 */
export default function Sidebar({ className = '', mobile = false, open = false, onClose }) {
  const { isAdmin, isSuperAdmin, workspace } = useAuth()
  const flags = useFeatureFlags()
  const { changesCount } = useWatchlist()
  const location = useLocation()

  // Mobile-mode: lock body scroll + Esc to close while drawer is open
  useEffect(() => {
    if (!mobile || !open) return
    document.body.style.overflow = 'hidden'
    const onKey = (e) => { if (e.key === 'Escape') onClose && onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = ''
      document.removeEventListener('keydown', onKey)
    }
  }, [mobile, open, onClose])

  // Mobile-mode: auto-close when route changes (user tapped a nav item)
  useEffect(() => {
    if (mobile && open && onClose) onClose()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search])

  const visible = (path) => !FLAG_FOR_PATH[path] || !flags[FLAG_FOR_PATH[path]]
  const appTitle = workspace?.brand_config?.app_title || null
  const logoUrl  = workspace?.brand_config?.logo_url  || null

  // Active-detection — phase 9 uses clean routes (/plans /roaming /esim /banners
  // /history) so we just match pathnames directly.
  const isPath = (path) => {
    if (path === '/') return location.pathname === '/'
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

  // Pure-button NavItems (search) need explicit close in mobile mode since
  // they don't trigger a route change.
  const afterNav = mobile ? onClose : undefined

  const body = (
    <>
      {/* Logo block */}
      <div style={{ padding: '18px 14px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <NavLink
          to="/"
          onClick={() => { afterNav && afterNav() }}
          style={{ textDecoration: 'none' }}
        >
          <Logo size="md" appTitle={appTitle} logoUrl={logoUrl} />
        </NavLink>
        {mobile && (
          <button
            onClick={onClose}
            aria-label="סגור תפריט"
            style={{
              width: 32,
              height: 32,
              borderRadius: 999,
              background: 'var(--color-moca-white, #fff)',
              border: '1px solid var(--color-moca-border)',
              color: 'var(--color-moca-sub)',
              fontSize: 18,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'inherit',
              lineHeight: 1,
              flexShrink: 0,
            }}
          >
            ×
          </button>
        )}
      </div>

      <nav style={{ padding: '8px 8px 16px', display: 'flex', flexDirection: 'column', gap: 1 }}>
        {/* ─── ניטור ─── */}
        <GroupLabel>ניטור</GroupLabel>
        <NavItem to="/" end icon={Icons.dashboard} label="דשבורד" isActive={isPath('/')} onAfterNav={afterNav} />
        {visible('/executive-summary') && (
          <NavItem to="/executive-summary" icon={Icons.exec} label="דוח מנהלים" isActive={isPath('/executive-summary')} onAfterNav={afterNav} />
        )}
        {visible('/positioning') && (
          <NavItem to="/positioning" icon={Icons.positioning} label="מיצוב תחרותי" isActive={isPath('/positioning')} onAfterNav={afterNav} />
        )}
        <NavItem to="/history" icon={Icons.history} label="היסטוריית שינויים" isActive={isPath('/history')} onAfterNav={afterNav} />
        {visible('/alerts') && (
          <NavItem
            to="/alerts"
            icon={Icons.alerts}
            label="התראות"
            badge={changesCount > 0 ? (changesCount > 99 ? '99+' : changesCount) : null}
            badgeColor="var(--color-moca-up)"
            isActive={isPath('/alerts')}
            onAfterNav={afterNav}
          />
        )}

        {/* ─── תובנות ─── */}
        <GroupLabel>תובנות</GroupLabel>
        {visible('/ai-insights') && (
          <NavItem to="/ai-insights" icon={Icons.ai} label="AI Insights" isActive={isPath('/ai-insights')} onAfterNav={afterNav} />
        )}
        <NavItem to="/banners" icon={Icons.banners} label="באנרים" isActive={isPath('/banners')} onAfterNav={afterNav} />
        {visible('/archive') && (
          <NavItem to="/archive" icon={Icons.archive} label="ארכיב Snapshots" isActive={isPath('/archive')} onAfterNav={afterNav} />
        )}

        {/* ─── מסלולים ─── */}
        <GroupLabel>מסלולים</GroupLabel>
        <NavItem to="/plans" icon={Icons.plans} label="השוואת מסלולים" isActive={isPath('/plans')} onAfterNav={afterNav} />
        <NavItem to="/roaming" icon={Icons.roaming} label={'חו״ל · Roaming'} isActive={isPath('/roaming')} onAfterNav={afterNav} />
        <NavItem to="/esim" icon={Icons.esim} label="eSIM גלובלי" isActive={isPath('/esim')} onAfterNav={afterNav} />
        <NavItem to="/resellers" icon={Icons.resellers} label="משווקים" isActive={isPath('/resellers')} onAfterNav={afterNav} />
        <NavItem to="/content" icon={Icons.content} label="תוכן" isActive={isPath('/content')} onAfterNav={afterNav} />

        {/* ─── כלים ─── */}
        <GroupLabel>כלים</GroupLabel>
        <NavItem
          icon={Icons.search}
          label={<span>חיפוש מתקדם <kbd style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'var(--color-moca-sand)', color: 'var(--color-moca-sub)', marginInlineStart: 6, fontFamily: 'inherit' }}>Ctrl K</kbd></span>}
          onClick={openSearch}
          onAfterNav={afterNav}
        />
        {(isAdmin || isSuperAdmin) && (
          <NavItem
            to={isSuperAdmin ? '/admin/workspaces' : '/workspace/users'}
            icon={Icons.workspace}
            label="Workspace"
            isActive={location.pathname.startsWith('/workspace') || location.pathname.startsWith('/admin')}
            onAfterNav={afterNav}
          />
        )}
      </nav>
    </>
  )

  // Mobile drawer mode — render as portal slide-in from RTL start (right)
  if (mobile) {
    if (!open) return null
    return createPortal(
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 9050,
          background: 'rgba(40,30,15,0.35)',
          backdropFilter: 'blur(2px)',
          WebkitBackdropFilter: 'blur(2px)',
          display: 'flex',
          justifyContent: 'flex-start',
          animation: 'fadeIn 200ms var(--ease-out)',
        }}
        role="dialog"
        aria-modal="true"
        aria-label="תפריט ניווט"
      >
        <aside
          onClick={(e) => e.stopPropagation()}
          style={{
            width: 280,
            maxWidth: '85vw',
            height: '100%',
            background: 'var(--color-moca-cream)',
            overflowY: 'auto',
            boxShadow: 'var(--sh-drawer)',
            direction: 'rtl',
            animation: 'drawerSlideIn 250ms var(--ease-out)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {body}
        </aside>
      </div>,
      document.body
    )
  }

  // Desktop sticky aside
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
      {body}
    </aside>
  )
}
