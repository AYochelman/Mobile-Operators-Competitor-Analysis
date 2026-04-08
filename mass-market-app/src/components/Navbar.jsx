import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Logo from './Logo'

const NAV_ITEMS = [
  { to: '/', label: 'דשבורד', icon: '📊', end: true },
  { to: '/compare', label: 'השוואה', icon: '⚖️' },
  { to: '/trends', label: 'מגמות', icon: '📈' },
  { to: '/alerts', label: 'התראות', icon: '🔔' },
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
                      ? 'text-gray-900 after:absolute after:bottom-0 after:inset-x-3 after:h-[1.5px] after:bg-gray-900 after:rounded-full'
                      : 'text-gray-400 hover:text-gray-600'
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
                      ? 'text-gray-900 after:absolute after:bottom-0 after:inset-x-3 after:h-[1.5px] after:bg-gray-900 after:rounded-full'
                      : 'text-gray-400 hover:text-gray-600'
                  }`
                }
              >
                הגדרות
              </NavLink>
            )}
          </nav>

          {/* User menu */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-400 hidden sm:inline">{user?.email}</span>
            <button
              onClick={signOut}
              className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors p-1"
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
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-md border-t border-gray-200/60">
        <div className="flex items-center justify-around h-12">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-1 px-3 transition-colors ${
                  isActive ? 'text-gray-900' : 'text-gray-400'
                }`
              }
            >
              <span className="text-base leading-none">{item.icon}</span>
              <span className="text-[9px] font-medium">{item.label}</span>
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-1 px-3 transition-colors ${
                  isActive ? 'text-gray-900' : 'text-gray-400'
                }`
              }
            >
              <span className="text-base leading-none">&#9881;&#65039;</span>
              <span className="text-[9px] font-medium">הגדרות</span>
            </NavLink>
          )}
        </div>
      </nav>
    </>
  )
}
