import { useScrape } from '../hooks/useScrape'

export default function ScrapeToast() {
  const { scraping, countdown, toast, dismissToast } = useScrape()

  if (!scraping && !toast) return null

  const formatTime = (secs) =>
    `${Math.floor(secs / 60)}:${(secs % 60).toString().padStart(2, '0')}`

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 pointer-events-none flex flex-col items-center gap-2">
      {scraping && (
        <div className="pointer-events-auto flex items-center gap-3 bg-moca-espresso text-white px-5 py-3 rounded-full shadow-lg text-sm font-medium">
          <svg className="animate-spin shrink-0" width="15" height="15" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 1 1-6.22-8.56" />
          </svg>
          <span>מעדכן נתונים...</span>
          {countdown > 0 && (
            <span className="font-mono bg-white/20 rounded-full px-2 py-0.5 text-xs">
              {formatTime(countdown)}
            </span>
          )}
        </div>
      )}

      {!scraping && toast && (
        <div
          className={`pointer-events-auto flex items-center gap-3 px-5 py-3 rounded-full shadow-lg text-sm font-medium
            ${toast.type === 'success'
              ? 'bg-green-600 text-white'
              : 'bg-red-500 text-white'}`}
        >
          {toast.type === 'success' ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          )}
          <span>{toast.message}</span>
          {toast.detail && (
            <span className="opacity-80 text-xs">{toast.detail}</span>
          )}
          <button onClick={dismissToast} className="mr-1 opacity-70 hover:opacity-100 transition-opacity">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
