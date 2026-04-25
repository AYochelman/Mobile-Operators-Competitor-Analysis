import { useScrape } from '../hooks/useScrape'

const STAGE_LABELS = {
  domestic: 'חבילות סלולר',
  abroad:   'חו"ל',
  global:   'גלובל / eSIM',
  content:  'שירותי תוכן',
  archive:  'שמירת ארכיון',
  banners:  'באנרים',
  all:      'סיכום',
}

const STAGE_ORDER = ['domestic', 'abroad', 'global', 'content', 'archive', 'banners']

export default function ScrapeProgressPanel() {
  const { scraping, progress } = useScrape()

  if (!scraping && progress.length === 0) return null

  // Group by stage — show latest status per stage
  const stageStatus = {}
  for (const ev of progress) {
    if (STAGE_ORDER.includes(ev.stage)) {
      stageStatus[ev.stage] = ev
    }
  }

  return (
    <div className="bg-white border border-moca-border/40 rounded-xl shadow-sm px-4 py-3 mb-4 text-right" dir="rtl">
      <div className="flex items-center gap-2 mb-2">
        {scraping && (
          <svg className="animate-spin text-moca-bolt" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 1 1-6.22-8.56" />
          </svg>
        )}
        <p className="text-xs font-semibold text-gray-700">
          {scraping ? 'התקדמות עדכון...' : 'עדכון אחרון'}
        </p>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {STAGE_ORDER.map(stage => {
          const ev = stageStatus[stage]
          let color = 'bg-gray-50 text-gray-300 border-gray-100'
          let icon = '—'
          if (ev?.status === 'starting') { color = 'bg-amber-50 text-amber-700 border-amber-200'; icon = '⏳' }
          if (ev?.status === 'done')     { color = 'bg-emerald-50 text-emerald-700 border-emerald-200'; icon = '✓' }
          if (ev?.status === 'error')    { color = 'bg-red-50 text-red-700 border-red-200'; icon = '✗' }
          return (
            <div key={stage} className={`border rounded-lg px-2 py-1.5 ${color}`}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[11px] font-medium">{STAGE_LABELS[stage]}</span>
                <span className="text-[10px]">{icon}</span>
              </div>
              {ev?.count != null && (
                <div className="text-[10px] opacity-75">{ev.count} פריטים</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
