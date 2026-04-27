import { useSearchParams } from 'react-router-dom'
import AlertsPriceTab from '../components/alerts/AlertsPriceTab'
import AlertsWatchlistTab from '../components/alerts/AlertsWatchlistTab'

const TABS = [
  { id: 'price',     label: 'התראות מחיר' },
  { id: 'watchlist', label: 'הגדרות Push ו-Watchlist' },
]

export default function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'watchlist' ? 'watchlist' : 'price'

  function selectTab(id) {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (id === 'price') next.delete('tab')
      else next.set('tab', id)
      return next
    })
  }

  return (
    <div className="max-w-6xl mx-auto px-4 pt-4">
      <div className="border-b border-moca-border/60 mb-4">
        <div className="flex gap-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => selectTab(t.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                tab === t.id
                  ? 'text-moca-text after:absolute after:bottom-0 after:inset-x-0 after:h-[2px] after:bg-moca-bolt'
                  : 'text-moca-muted hover:text-moca-text'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'price' && <AlertsPriceTab />}
      {tab === 'watchlist' && <AlertsWatchlistTab />}
    </div>
  )
}
