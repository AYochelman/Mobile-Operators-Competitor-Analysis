import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { ScrapeProvider } from './hooks/useScrape'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ComparePage from './pages/ComparePage'
// import TrendsPage from './pages/TrendsPage'  // removed
import AlertsPage from './pages/AlertsPage'
import ExecutiveSummaryPage from './pages/ExecutiveSummaryPage'
import ArchivePage from './pages/ArchivePage'
import SettingsPage from './pages/SettingsPage'
import WorkspacesAdminPage from './pages/WorkspacesAdminPage'
import NotFoundPage from './pages/NotFoundPage'
import OfflineBanner from './components/OfflineBanner'

function ProtectedRoute({ children, adminOnly = false, superAdminOnly = false }) {
  const { user, loading, isAdmin, isSuperAdmin } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen"><div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" /></div>
  if (!user) return <Navigate to="/login" replace />
  if (superAdminOnly && !isSuperAdmin) return <Navigate to="/" replace />
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <ScrapeProvider>
      <OfflineBanner />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="compare" element={<ComparePage />} />
          {/* trends page removed */}
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="executive-summary" element={<ExecutiveSummaryPage />} />
          <Route path="archive" element={<ArchivePage />} />
          <Route path="settings" element={<ProtectedRoute adminOnly><SettingsPage /></ProtectedRoute>} />
          <Route path="admin/workspaces" element={<ProtectedRoute superAdminOnly><WorkspacesAdminPage /></ProtectedRoute>} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </ScrapeProvider>
  )
}
