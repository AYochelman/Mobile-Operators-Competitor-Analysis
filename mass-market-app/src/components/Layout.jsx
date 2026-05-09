import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'
import ChatPanel from './ChatPanel'
import ScrapeToast from './ScrapeToast'
import ViewAsBanner from './ViewAsBanner'
import Sidebar from './moca/Sidebar'
import Topbar from './moca/Topbar'
import TimeMachineModal from './moca/TimeMachineModal'
import { useFeatureFlags } from '../hooks/useFeatureFlags'

export default function Layout() {
  const flags = useFeatureFlags()
  const [tmOpen, setTmOpen] = useState(false)

  return (
    <div className="min-h-screen flex flex-col bg-moca-bg">
      {/* Super-admin "viewing as workspace X" banner — stacks above shell */}
      <ViewAsBanner />

      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        {/* Desktop sidebar (RTL: renders on the physical right as first flex-row child) */}
        <Sidebar />

        {/* Main column: topbar + content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Mobile top bar — Navbar's <header> hides on md+ via md:hidden.
              Mobile bottom-nav also lives inside Navbar and stays visible. */}
          <Navbar />

          {/* Desktop topbar */}
          <Topbar onTimeMachine={() => setTmOpen(true)} />

          <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
            <Outlet />
          </main>
        </div>
      </div>

      {!flags.hide_chat && <ChatPanel />}
      <ScrapeToast />
      <TimeMachineModal open={tmOpen} onClose={() => setTmOpen(false)} />
    </div>
  )
}
