import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar'
import ChatPanel from './ChatPanel'
import ScrapeToast from './ScrapeToast'
import ViewAsBanner from './ViewAsBanner'
import ErrorBoundary from './ErrorBoundary'
import Sidebar from './moca/Sidebar'
import Topbar from './moca/Topbar'
import TimeMachineModal from './moca/TimeMachineModal'
import { useFeatureFlags } from '../hooks/useFeatureFlags'

export default function Layout() {
  const flags = useFeatureFlags()
  const location = useLocation()
  const [tmOpen, setTmOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

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
          <Navbar onMobileMenuOpen={() => setMobileNavOpen(true)} />

          {/* Desktop topbar */}
          <Topbar onTimeMachine={() => setTmOpen(true)} />

          <main className="flex-1 overflow-y-auto pb-28 md:pb-0">
            {/* ErrorBoundary keyed on pathname: if a route crashes, navigating
                to a different one auto-resets the boundary instead of
                requiring "נסה שוב". The shell (sidebar + topbar) stays mounted. */}
            <ErrorBoundary key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>

      {/* Mobile sidebar drawer — same content as desktop, hamburger-triggered */}
      <Sidebar mobile open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

      {!flags.hide_chat && <ChatPanel />}
      <ScrapeToast />
      <TimeMachineModal open={tmOpen} onClose={() => setTmOpen(false)} />
    </div>
  )
}
