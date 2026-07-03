import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import { useWatchlist } from '../../hooks/useWatchlist'
import { useLang } from '../../hooks/useLanguage'
import { FLAG_FOR_PATH } from '../../data/navFlags'
import Logo from '../Logo'

/**
 * Right-side sidebar (RTL start) — primary navigation per MOCA design handoff.
 * Groups: ניטור / תובנות / מסלולים / כלים. Routes that live as tabs on the
 * dashboard (?tab=history, ?tab=banners, ?tab=abroad, ?tab=global) are
 * deep-linked rather than full pages.
 */

// FLAG_FOR_PATH (path → feature-flag that hides the nav item) lives in
// ../../data/navFlags so Sidebar, Navbar and the admin panel stay in sync.

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
  usa: (
    <svg {...ICON_PROPS}><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3.5c-.5-.5-2.5 0-4 1.5L13.5 8 5.2 6.2c-.5-.1-.9.2-.9.7l.3.5L8 11l-3 1-1 1 .5.5L8 15l1 3.5.5.5 1-1 1-3 3.5 2.7.5.3c.5 0 .8-.4.7-.9z"/></svg>
  ),
  resellers: (
    <svg {...ICON_PROPS}><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
  ),
  content: (
    <svg {...ICON_PROPS}><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><path d="M7 8l2 2-2 2M11 12h6"/></svg>
  ),
  news: (
    <svg {...ICON_PROPS}><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8M15 18h-5M10 6h8v4h-8V6Z"/></svg>
  ),
  social: (
    <svg {...ICON_PROPS}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
  ),
  compare: (
    <svg {...ICON_PROPS}><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
  ),
  search: (
    <svg {...ICON_PROPS}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
  ),
  usage: (
    <svg {...ICON_PROPS}><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/><circle cx="12" cy="12" r="3"/></svg>
  ),
  userActivity: (
    <svg {...ICON_PROPS}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 11h-6M22 15h-6"/></svg>
  ),
  hotels: (
    <svg {...ICON_PROPS}><path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-3"/><path d="M9 9v.01M9 12v.01M9 15v.01M9 18v.01"/></svg>
  ),
  external: (
    <svg {...ICON_PROPS}><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>
  ),
  deals: (
    <svg {...ICON_PROPS}><path d="M4 7h16v13H4z"/><path d="M2 7h20"/><path d="M12 20V7"/><path d="M12 7S11 2 7.5 2a2.5 2.5 0 0 0 0 5H12z"/><path d="M12 7s1-5 4.5-5a2.5 2.5 0 0 1 0 5H12z"/></svg>
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
        padding: '6px 12px',
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
        padding: '10px 14px 4px',
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
  const { isSuperAdmin, workspace } = useAuth()
  const flags = useFeatureFlags()
  const { changesCount } = useWatchlist()
  const { dir, tt } = useLang()
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
      <div style={{ padding: '12px 14px 6px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
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
            aria-label={tt('סגור תפריט', 'Close menu')}
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

      <nav style={{ padding: '4px 8px 10px', display: 'flex', flexDirection: 'column', gap: 1 }}>
        {/* ─── Monitoring ─── */}
        {(visible('/') || visible('/executive-summary') || visible('/positioning') || visible('/history') || visible('/alerts')) && (
          <GroupLabel>{tt('ניטור', 'Monitoring')}</GroupLabel>
        )}
        {visible('/') && (
          <NavItem to="/" end icon={Icons.dashboard} label={tt('דשבורד', 'Dashboard')} isActive={isPath('/')} onAfterNav={afterNav} />
        )}
        {visible('/executive-summary') && (
          <NavItem to="/executive-summary" icon={Icons.exec} label={tt('דוח מנהלים', 'Executive report')} isActive={isPath('/executive-summary')} onAfterNav={afterNav} />
        )}
        {visible('/positioning') && (
          <NavItem to="/positioning" icon={Icons.positioning} label={tt('מיצוב תחרותי', 'Positioning')} isActive={isPath('/positioning')} onAfterNav={afterNav} />
        )}
        {visible('/history') && (
          <NavItem to="/history" icon={Icons.history} label={tt('היסטוריית שינויים', 'Change history')} isActive={isPath('/history')} onAfterNav={afterNav} />
        )}
        {visible('/alerts') && (
          <NavItem
            to={changesCount > 0 ? '/alerts?tab=watchlist' : '/alerts'}
            icon={Icons.alerts}
            label={tt('התראות', 'Alerts')}
            badge={changesCount > 0 ? (changesCount > 99 ? '99+' : changesCount) : null}
            badgeColor="var(--color-moca-up)"
            isActive={isPath('/alerts')}
            onAfterNav={afterNav}
          />
        )}

        {/* ─── Insights ─── */}
        {(visible('/ai-insights') || visible('/news') || visible('/social') || visible('/banners') || visible('/archive')) && (
          <GroupLabel>{tt('תובנות', 'Insights')}</GroupLabel>
        )}
        {visible('/ai-insights') && (
          <NavItem to="/ai-insights" icon={Icons.ai} label="AI Insights" isActive={isPath('/ai-insights')} onAfterNav={afterNav} />
        )}
        {visible('/news') && (
          <NavItem to="/news" icon={Icons.news} label={tt('בחדשות', 'In the news')} isActive={isPath('/news')} onAfterNav={afterNav} />
        )}
        {visible('/social') && (
          <NavItem to="/social" icon={Icons.social} label={tt('ברשתות החברתיות', 'On social')} isActive={isPath('/social')} onAfterNav={afterNav} />
        )}
        {visible('/banners') && (
          <NavItem to="/banners" icon={Icons.banners} label={tt('באנרים', 'Banners')} isActive={isPath('/banners')} onAfterNav={afterNav} />
        )}
        {visible('/archive') && (
          <NavItem to="/archive" icon={Icons.archive} label={tt('מכונת זמן', 'Time Machine')} isActive={isPath('/archive')} onAfterNav={afterNav} />
        )}

        {/* ─── Plans ─── */}
        {(visible('/plans') || visible('/roaming') || visible('/esim') || visible('/usa') || visible('/resellers') || visible('/content') || visible('/compare')) && (
          <GroupLabel>{tt('מסלולים', 'Plans')}</GroupLabel>
        )}
        {visible('/plans') && (
          <NavItem to="/plans" icon={Icons.plans} label="Mass Market" isActive={isPath('/plans')} onAfterNav={afterNav} />
        )}
        {visible('/roaming') && (
          <NavItem to="/roaming" icon={Icons.roaming} label={tt('חו״ל · Roaming', 'Roaming')} isActive={isPath('/roaming')} onAfterNav={afterNav} />
        )}
        {visible('/esim') && (
          <NavItem to="/esim" icon={Icons.esim} label={tt('eSIM גלובלי', 'Global eSIM')} isActive={isPath('/esim')} onAfterNav={afterNav} />
        )}
        {visible('/usa') && (
          <NavItem to="/usa" icon={Icons.usa} label={tt('נוחתים בארה״ב', 'USA')} isActive={isPath('/usa')} onAfterNav={afterNav} />
        )}
        {visible('/resellers') && (
          <NavItem to="/resellers" icon={Icons.resellers} label={tt('משווקים', 'Resellers')} isActive={isPath('/resellers')} onAfterNav={afterNav} />
        )}
        {visible('/content') && (
          <NavItem to="/content" icon={Icons.content} label={tt('תוכן', 'Content')} isActive={isPath('/content')} onAfterNav={afterNav} />
        )}
        {visible('/compare') && (
          <NavItem to="/compare" icon={Icons.compare} label={tt('השוואת מחירים', 'Price compare')} isActive={isPath('/compare')} onAfterNav={afterNav} />
        )}

        {/* ─── Tools ─── */}
        <GroupLabel>{tt('כלים', 'Tools')}</GroupLabel>
        <NavItem
          icon={Icons.search}
          label={<span>{tt('חיפוש מתקדם', 'Advanced search')} <kbd style={{ fontSize: 9, padding: '1px 4px', borderRadius: 3, background: 'var(--color-moca-sand)', color: 'var(--color-moca-sub)', marginInlineStart: 6, fontFamily: 'inherit' }}>Ctrl K</kbd></span>}
          onClick={openSearch}
          onAfterNav={afterNav}
        />
        {isSuperAdmin && (
          <NavItem
            to="/usage"
            icon={Icons.usage}
            label={tt('שימוש ב-Claude', 'Claude usage')}
            isActive={isPath('/usage')}
            onAfterNav={afterNav}
          />
        )}
        {/* פעילות משתמשים moved to הגדרות מערכת → ניהול משתמשים tab;
            פורטלי אורחים + eSIM (B2C) dashboard/page moved to the profile menu. */}
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
        aria-label={tt('תפריט ניווט', 'Navigation menu')}
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
            direction: dir,
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
