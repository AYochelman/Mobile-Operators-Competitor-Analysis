import { NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { useWatchlist } from '../hooks/useWatchlist'
import Logo from './Logo'
import NavDropdown from './NavDropdown'
import MobileMoreSheet from './MobileMoreSheet'

const NAV_ICONS = {
  '/': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
    </svg>
  ),
  '/compare': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  ),
  '/alerts': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  ),
  '/executive-summary': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  ),
  more: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  ),
}

const FLAG_FOR_PATH = {
  '/compare':           'hide_compare',
  '/positioning':       'hide_positioning',
  '/alerts':            'hide_alerts',
  '/executive-summary': 'hide_executive_summary',
  '/archive':           'hide_archive',
  '/ai-insights':       'hide_ai_insights',
}

const itemCls = ({ isActive }) =>
  `block px-4 py-2 text-[13px] transition-colors ${
    isActive
      ? 'text-moca-bolt bg-moca-cream font-medium'
      : 'text-moca-text hover:bg-gray-50'
  }`

export default function Navbar() {
  const { user, isAdmin, isSuperAdmin, signOut, workspace } = useAuth()
  const flags = useFeatureFlags()
  const { changesCount } = useWatchlist()
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)

  const appTitle = workspace?.brand_config?.app_title || null
  const logoUrl  = workspace?.brand_config?.logo_url  || null

  const visible = (path) => !FLAG_FOR_PATH[path] || !flags[FLAG_FOR_PATH[path]]

  // ---------- Group definitions (used by both desktop dropdowns and mobile sheet) ----------
  const groups = [
    {
      key: 'analysis',
      label: 'ניתוח', // ניתוח
      items: [
        { to: '/',        label: 'דשבורד', visible: true },
        { to: '/compare', label: 'השוואה', visible: visible('/compare') },
        { to: '/alerts',  label: 'התראות', visible: visible('/alerts') },
      ],
    },
    {
      key: 'insights',
      label: 'תובנות', // תובנות
      items: [
        { to: '/executive-summary', label: 'תקציר מנהלים', visible: visible('/executive-summary') },
        { to: '/positioning',       label: 'מיצוב תחרותי',          visible: visible('/positioning') },
        { to: '/ai-insights',       label: 'AI Insights',                                          visible: visible('/ai-insights') },
      ],
    },
    {
      key: 'history',
      label: 'היסטוריה', // היסטוריה
      items: [
        { to: '/archive',      label: 'ארכיב snapshots', visible: visible('/archive') },
        { to: '/?tab=history', label: 'שינויי היסטוריה', visible: true },
      ],
    },
    {
      key: 'admin',
      label: 'ניהול', // ניהול
      items: [
        { to: '/workspace/users',    label: 'הצוות',         visible: isAdmin },
        { to: '/workspace/settings', label: 'מיתוג',         visible: isAdmin },
        { to: '/settings',           label: 'הגדרות', visible: isAdmin },
        { to: '/admin/workspaces',   label: 'Workspaces',                            visible: isSuperAdmin },
        { to: '/admin/audit',        label: 'יומן ביקורת', visible: isSuperAdmin },
      ],
    },
  ]
    .map(g => ({ ...g, items: g.items.filter(i => i.visible) }))
    .filter(g => g.items.length > 0)

  function isGroupActive(group) {
    return group.items.some(i => {
      if (i.to === '/') return location.pathname === '/' && !location.search.includes('tab=history')
      if (i.to === '/?tab=history') return location.pathname === '/' && location.search.includes('tab=history')
      return location.pathname === i.to || location.pathname.startsWith(i.to + '/')
    })
  }

  // ---------- Mobile bottom-bar (5 items: 4 visible + עוד) ----------
  const mobileBarItems = [
    { to: '/',                  label: 'דשבורד', icon: NAV_ICONS['/'],                  visible: true },
    { to: '/compare',           label: 'השוואה', icon: NAV_ICONS['/compare'],           visible: visible('/compare') },
    { to: '/alerts',            label: 'התראות', icon: NAV_ICONS['/alerts'],            visible: visible('/alerts') },
    { to: '/executive-summary', label: 'תקציר',       icon: NAV_ICONS['/executive-summary'], visible: visible('/executive-summary') },
  ].filter(i => i.visible)

  // ---------- Mobile sheet sections ----------
  const sheetSections = groups.map(g => ({
    title: g.label,
    items: g.items.map(i => (
      <NavLink
        key={i.to}
        to={i.to}
        end={i.to === '/'}
        className={itemCls}
      >
        {i.label}
      </NavLink>
    )),
  }))

  return (
    <>
      {/* Desktop header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-200/60 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 h-12 flex items-center justify-between">
          <NavLink to="/" className="flex items-center">
            <Logo size="md" appTitle={appTitle} logoUrl={logoUrl} />
          </NavLink>

          <nav className="hidden md:flex items-center gap-2">
            {groups.map(g => (
              <NavDropdown key={g.key} label={g.label} isActive={isGroupActive(g)}>
                {g.items.map(i => (
                  <NavLink key={i.to} to={i.to} end={i.to === '/'} className={itemCls}>
                    {i.label}
                  </NavLink>
                ))}
              </NavDropdown>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <span className="text-[11px] text-moca-sub hidden sm:inline">{user?.email}</span>
            <NavLink
              to="/alerts?tab=watchlist"
              className="relative text-moca-sub hover:text-moca-bolt transition-colors p-1"
              title="התראות מעקב"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              {changesCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 bg-red-500 text-white text-[8px] font-bold rounded-full flex items-center justify-center px-0.5 leading-none">
                  {changesCount > 9 ? '9+' : changesCount}
                </span>
              )}
            </NavLink>
            <NavLink
              to="/preferences"
              className="text-moca-sub hover:text-moca-bolt transition-colors p-1"
              title="העדפות"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </NavLink>
            <button
              onClick={signOut}
              className="text-[11px] text-moca-sub hover:text-moca-bolt transition-colors p-1"
              title="יציאה"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile bottom-bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-md border-t border-moca-border/60">
        <div className="flex items-center justify-around h-14">
          {mobileBarItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-1.5 px-3 transition-colors ${
                  isActive ? 'text-moca-bolt' : 'text-moca-muted'
                }`
              }
            >
              {item.icon}
              <span className="text-[9px] font-medium">{item.label}</span>
            </NavLink>
          ))}
          <button
            onClick={() => setMoreOpen(true)}
            className="flex flex-col items-center gap-0.5 py-1.5 px-3 transition-colors text-moca-muted"
          >
            {NAV_ICONS.more}
            <span className="text-[9px] font-medium">{'עוד'}</span>
          </button>
        </div>
      </nav>

      <MobileMoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} sections={sheetSections} />
    </>
  )
}
