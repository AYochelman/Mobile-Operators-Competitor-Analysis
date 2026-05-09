import { useSearchParams } from 'react-router-dom'
import AlertsPriceTab from '../components/alerts/AlertsPriceTab'
import AlertsWatchlistTab from '../components/alerts/AlertsWatchlistTab'
import { PageHeader } from '../components/moca'

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
    <>
      <PageHeader
        kicker="ניטור · התראות"
        title="התראות מחיר ו-Watchlist"
        subtitle="התראות שוטפות + מסלולים שאתה עוקב אחריהם להתראות Push."
        tabs={TABS}
        activeTab={tab}
        onTabChange={selectTab}
      />
      <div className="max-w-[1320px] mx-auto px-8 pb-8 pt-4">
        {tab === 'price' && <AlertsPriceTab />}
        {tab === 'watchlist' && <AlertsWatchlistTab />}
      </div>
    </>
  )
}
