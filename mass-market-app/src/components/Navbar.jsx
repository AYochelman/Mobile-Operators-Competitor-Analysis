import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Logo from './Logo'

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
  '/trends': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  '/alerts': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  ),
  '/settings': (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
}

const NAV_ITEMS = [
  { to: '/', label: 'דשבורד', end: true },
  { to: '/compare', label: 'השוואה' },
  { to: '/alerts', label: 'התראות' },
]

export default function Navbar() {
  const { user, isAdmin, signOut } = useAuth()

  return (
    <>
      {/* Desktop header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-200/60 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 h-12 flex items-center justify-between">
          {/* Logo */}
          <NavLink to="/" className="flex items-center">
            <Logo size="md" />
          </NavLink>

          {/* Nav links - desktop */}
          <nav className="hidden md:flex items-center gap-0.5">
            {NAV_ITEMS.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `px-3 py-1.5 text-[13px] font-medium transition-all duration-150 relative ${
                    isActive
                      ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-3 after:h-[1.5px] after:bg-moca-bolt after:rounded-full'
                      : 'text-moca-muted hover:text-moca-bolt'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            {isAdmin && (
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  `px-3 py-1.5 text-[13px] font-medium transition-all duration-150 relative ${
                    isActive
                      ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-3 after:h-[1.5px] after:bg-moca-bolt after:rounded-full'
                      : 'text-moca-muted hover:text-moca-bolt'
                  }`
                }
              >
                הגדרות
              </NavLink>
            )}
          </nav>

          {/* User menu */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-moca-sub hidden sm:inline">{user?.email}</span>
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

      {/* Mobile bottom bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-md border-t border-moca-border/60">
        <div className="flex items-center justify-around h-14">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-1.5 px-3 transition-colors ${
                  isActive ? 'text-moca-bolt' : 'text-moca-muted'
                }`
              }
            >
              {NAV_ICONS[item.to]}
              <span className="text-[9px] font-medium">{item.label}</span>
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-1.5 px-3 transition-colors ${
                  isActive ? 'text-moca-bolt' : 'text-moca-muted'
                }`
              }
            >
              {NAV_ICONS['/settings']}
              <span className="text-[9px] font-medium">הגדרות</span>
            </NavLink>
          )}
        </div>
      </nav>
    </>
  )
}
