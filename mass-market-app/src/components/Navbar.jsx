import { useState, useEffect, useRef } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useFeatureFlags } from '../hooks/useFeatureFlags'
import { useWatchlist } from '../hooks/useWatchlist'
import Logo from './Logo'
import NavDropdown from './NavDropdown'
import MobileMoreSheet from './MobileMoreSheet'

const GROUP_ICONS = {
  analysis: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  ),
  insights: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18h6" /><path d="M10 22h4" /><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.2 1 2v1.3h6v-1.3c0-.8.4-1.5 1-2A7 7 0 0 0 12 2z" />
    </svg>
  ),
  history: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  admin: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
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

function ProfileMenu({ user, isAdmin, isSuperAdmin, signOut }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onEsc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  const go = (path) => { setOpen(false); navigate(path) }

  const initial = (user?.email || '?')[0]?.toUpperCase()
  const itemCls = 'w-full text-right px-3 py-2 text-[12px] text-moca-text hover:bg-moca-cream rounded-md transition-colors flex items-center justify-between'

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-7 h-7 rounded-full bg-moca-cream text-moca-bolt text-[11px] font-bold flex items-center justify-center hover:ring-2 hover:ring-moca-bolt/30 transition-all"
        title={user?.email || 'פרופיל'}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        {initial}
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 min-w-[200px] bg-white rounded-xl shadow-xl border border-moca-border/40 p-1.5 z-50 animate-fade-in">
          <div className="px-3 py-2 text-[10px] text-moca-sub border-b border-moca-border/30 mb-1 truncate" dir="ltr">{user?.email}</div>
          <button onClick={() => go('/preferences')} className={itemCls}>העדפות</button>
          <button onClick={() => go('/alerts?tab=watchlist')} className={itemCls}>הגדרות התראות</button>
          {isAdmin && !isSuperAdmin && (
            <>
              <div className="h-px bg-moca-border/30 my-1" />
              <button onClick={() => go('/workspace/users')} className={itemCls}>הצוות</button>
              <button onClick={() => go('/workspace/settings')} className={itemCls}>מיתוג Workspace</button>
            </>
          )}
          {isAdmin && (
            <button onClick={() => go('/settings')} className={itemCls}>הגדרות מערכת</button>
          )}
          {isSuperAdmin && (
            <>
              <div className="h-px bg-moca-border/30 my-1" />
              <button onClick={() => go('/admin/workspaces')} className={itemCls}>Workspaces</button>
              <button onClick={() => go('/admin/audit')} className={itemCls}>יומן ביקורת</button>
            </>
          )}
          <div className="h-px bg-moca-border/30 my-1" />
          <button onClick={() => { setOpen(false); signOut() }} className={`${itemCls} text-red-600 hover:bg-red-50`}>יציאה</button>
        </div>
      )}
    </div>
  )
}

const dropdownItemCls = ({ isActive }) =>
  `block px-4 py-2 text-[13px] transition-colors ${
    isActive
      ? 'text-moca-bolt bg-moca-cream font-medium'
      : 'text-moca-text hover:bg-gray-50'
  }`

export default function Navbar({ onMobileMenuOpen }) {
  const { user, isAdmin, isSuperAdmin, signOut, workspace } = useAuth()
  const flags = useFeatureFlags()
  const { changesCount } = useWatchlist()
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)
  const [activeGroupKey, setActiveGroupKey] = useState(null)

  const appTitle = workspace?.brand_config?.app_title || null
  const logoUrl  = workspace?.brand_config?.logo_url  || null

  const visible = (path) => !FLAG_FOR_PATH[path] || !flags[FLAG_FOR_PATH[path]]

  // ---------- Group definitions (used by both desktop dropdowns and mobile sheet) ----------
  const groups = [
    {
      key: 'analysis',
      label: 'ניתוח',
      items: [
        { to: '/',        label: 'דשבורד', visible: true },
        { to: '/compare', label: 'השוואה', visible: visible('/compare') },
        { to: '/alerts',  label: 'התראות', visible: visible('/alerts') },
      ],
    },
    {
      key: 'insights',
      label: 'תובנות',
      items: [
        { to: '/executive-summary', label: 'תקציר מנהלים', visible: visible('/executive-summary') },
        { to: '/positioning',       label: 'מיצוב תחרותי', visible: visible('/positioning') },
        { to: '/ai-insights',       label: 'AI Insights',  visible: visible('/ai-insights') },
      ],
    },
    {
      key: 'history',
      label: 'היסטוריה',
      items: [
        { to: '/archive',      label: 'ארכיב snapshots', visible: visible('/archive') },
        { to: '/?tab=history', label: 'שינויי היסטוריה', visible: true },
      ],
    },
    {
      key: 'admin',
      label: 'ניהול',
      items: [
        { to: '/workspace/users',    label: 'הצוות',         visible: isAdmin },
        { to: '/workspace/settings', label: 'מיתוג',         visible: isAdmin },
        { to: '/settings',           label: 'הגדרות',        visible: isAdmin },
        { to: '/admin/workspaces',   label: 'Workspaces',    visible: isSuperAdmin },
        { to: '/admin/audit',        label: 'יומן ביקורת',   visible: isSuperAdmin },
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

  // ---------- Mobile sheet sections ----------
  // Mirror desktop: bottom bar shows the same 4 group buttons as the desktop dropdowns.
  // Tapping a group opens MobileMoreSheet filtered to that group's items only.
  const allSheetSections = groups.map(g => ({
    key: g.key,
    title: g.label,
    items: g.items.map(i => (
      <NavLink
        key={i.to}
        to={i.to}
        end={i.to === '/'}
        className={dropdownItemCls}
      >
        {i.label}
      </NavLink>
    )),
  }))
  const sheetSections = activeGroupKey
    ? allSheetSections.filter(s => s.key === activeGroupKey)
    : allSheetSections

  function openGroup(key) {
    setActiveGroupKey(key)
    setMoreOpen(true)
  }
  function closeSheet() {
    setMoreOpen(false)
    setActiveGroupKey(null)
  }

  return (
    <>
      {/* Mobile top header — replaced on desktop by <Topbar> in Layout */}
      <header className="md:hidden bg-white/80 backdrop-blur-md border-b border-gray-200/60 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 h-12 flex items-center justify-between">
          <NavLink to="/" className="flex items-center">
            <Logo size="md" appTitle={appTitle} logoUrl={logoUrl} />
          </NavLink>

          <nav className="hidden md:flex items-center gap-2">
            {groups.map(g => (
              <NavDropdown key={g.key} label={g.label} isActive={isGroupActive(g)}>
                {g.items.map(i => (
                  <NavLink key={i.to} to={i.to} end={i.to === '/'} className={dropdownItemCls}>
                    {i.label}
                  </NavLink>
                ))}
              </NavDropdown>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            {onMobileMenuOpen && (
              <button
                onClick={onMobileMenuOpen}
                className="text-moca-sub hover:text-moca-bolt transition-colors p-1"
                title="פתח תפריט"
                aria-label="פתח תפריט"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
            )}
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
            <ProfileMenu user={user} isAdmin={isAdmin} isSuperAdmin={isSuperAdmin} signOut={signOut} />
          </div>
        </div>
      </header>

      {/* Mobile bottom-bar — mirrors desktop's 4 dropdown groups */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-md border-t border-moca-border/60">
        <div className="flex items-center justify-around h-14">
          {groups.map(g => {
            const active = isGroupActive(g)
            return (
              <button
                key={g.key}
                onClick={() => openGroup(g.key)}
                className={`flex flex-col items-center gap-0.5 py-1.5 px-3 transition-colors ${
                  active ? 'text-moca-bolt' : 'text-moca-muted'
                }`}
                aria-haspopup="menu"
                aria-expanded={moreOpen && activeGroupKey === g.key}
              >
                {GROUP_ICONS[g.key]}
                <span className="text-[9px] font-medium">{g.label}</span>
              </button>
            )
          })}
        </div>
      </nav>

      <MobileMoreSheet
        open={moreOpen}
        onClose={closeSheet}
        sections={sheetSections}
        title={activeGroupKey ? (allSheetSections.find(s => s.key === activeGroupKey)?.title || 'תפריט') : 'תפריט'}
      />
    </>
  )
}
