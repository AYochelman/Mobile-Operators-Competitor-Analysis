import { useSearchParams } from 'react-router-dom'
import AlertsPriceTab from '../components/alerts/AlertsPriceTab'
import AlertsWatchlistTab from '../components/alerts/AlertsWatchlistTab'
import { PageHeader } from '../components/moca'
import { useWatchlist } from '../hooks/useWatchlist'
import { useLang } from '../hooks/useLanguage'

export default function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { changesCount } = useWatchlist()
  const { tt } = useLang()
  const tab = searchParams.get('tab') === 'watchlist' ? 'watchlist' : 'price'

  // Surface the unread watched-changes count on the watchlist tab so it's clear
  // where the sidebar/topbar "התראות" badge is pointing.
  const TABS = [
    { id: 'price',     label: tt('התראות מחיר', 'Price alerts') },
    { id: 'watchlist', label: tt('הגדרות Push ו-Watchlist', 'Push & Watchlist settings'), count: changesCount > 0 ? changesCount : undefined },
  ]

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
        kicker={tt('ניטור · התראות', 'Monitoring · Alerts')}
        title={tt('התראות מחיר ו-Watchlist', 'Price alerts & Watchlist')}
        subtitle={tt('התראות שוטפות + מסלולים שאתה עוקב אחריהם להתראות Push.', 'Ongoing alerts + plans you follow for Push notifications.')}
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
