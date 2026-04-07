import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const NAV_ITEMS = [
  { to: '/', label: '📊 דשבורד', end: true },
  { to: '/compare', label: '⚖️ השוואה' },
  { to: '/trends', label: '📈 מגמות' },
  { to: '/alerts', label: '🔔 התראות' },
]

export default function Navbar() {
  const { user, isAdmin, signOut } = useAuth()

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <NavLink to="/" className="flex flex-col">
          <span className="text-xl font-bold text-blue-600">Mobile carriers Competitor Analysis</span>
          <span className="text-xs text-gray-400">Made By Alon Yochelman</span>
        </NavLink>

        {/* Nav links - desktop */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
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
                `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              ⚙️ הגדרות
            </NavLink>
          )}
        </nav>

        {/* User menu */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 hidden sm:inline">{user?.email}</span>
          <button
            onClick={signOut}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors"
          >
            יציאה
          </button>
        </div>
      </div>

      {/* Nav links - mobile bottom bar */}
      <nav className="md:hidden flex items-center justify-around border-t border-gray-100 bg-white">
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex-1 text-center py-2.5 text-xs font-medium transition-colors ${
                isActive ? 'text-blue-600 border-t-2 border-blue-600' : 'text-gray-500'
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
              `flex-1 text-center py-2.5 text-xs font-medium transition-colors ${
                isActive ? 'text-blue-600 border-t-2 border-blue-600' : 'text-gray-500'
              }`
            }
          >
            ⚙️
          </NavLink>
        )}
      </nav>
    </header>
  )
}
