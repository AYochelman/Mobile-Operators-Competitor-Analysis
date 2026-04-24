import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'
import ChatPanel from './ChatPanel'
import ScrapeToast from './ScrapeToast'
import { useFeatureFlags } from '../hooks/useFeatureFlags'

export default function Layout() {
  const flags = useFeatureFlags()
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
      {!flags.hide_chat && <ChatPanel />}
      <ScrapeToast />
    </div>
  )
}
