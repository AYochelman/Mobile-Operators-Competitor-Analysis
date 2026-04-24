import { useAuth } from '../hooks/useAuth'

export default function ViewAsBanner() {
  const { viewAs, exitViewAs } = useAuth()
  if (!viewAs) return null

  return (
    <div className="bg-indigo-600 text-white text-sm sticky top-0 z-[60] shadow-sm">
      <div className="max-w-6xl mx-auto px-4 py-2 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <span className="truncate">
            צופה כ-<strong>{viewAs.name}</strong>
            <span className="mx-1.5 text-indigo-200">·</span>
            <code className="text-[11px] opacity-80">{viewAs.slug}</code>
          </span>
        </div>
        <button
          onClick={exitViewAs}
          className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 rounded-lg px-3 py-1 text-xs font-medium transition-colors"
        >
          יציאה ממצב צפייה
          <span className="text-base leading-none">×</span>
        </button>
      </div>
    </div>
  )
}
