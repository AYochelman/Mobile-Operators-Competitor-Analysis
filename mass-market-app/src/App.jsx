import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { ScrapeProvider } from './hooks/useScrape'
import { getMvnoColors } from './data/mvnoBrandColors'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ComparePage from './pages/ComparePage'
// import TrendsPage from './pages/TrendsPage'  // removed
import AlertsPage from './pages/AlertsPage'
import ExecutiveSummaryPage from './pages/ExecutiveSummaryPage'
import ArchivePage from './pages/ArchivePage'
import SettingsPage from './pages/SettingsPage'
import PreferencesPage from './pages/PreferencesPage'
import WorkspacesAdminPage from './pages/WorkspacesAdminPage'
import WorkspaceUsersPage from './pages/WorkspaceUsersPage'
import WorkspaceBrandingPage from './pages/WorkspaceBrandingPage'
import AuditLogPage from './pages/AuditLogPage'
import InvitePage from './pages/InvitePage'
import SuspendedPage from './pages/SuspendedPage'
import NotFoundPage from './pages/NotFoundPage'
import OfflineBanner from './components/OfflineBanner'

function BrandThemeApplier() {
  const { workspace } = useAuth()
  useEffect(() => {
    const root = document.documentElement
    const cfg = workspace?.brand_config || {}
    // Precedence: explicit brand_config override → MVNO default color → unset (moca theme)
    const mvnoColors = getMvnoColors(workspace?.mvno_carrier)
    const primary   = cfg.primary_color   || mvnoColors?.primary
    const secondary = cfg.secondary_color || mvnoColors?.secondary
    if (primary) {
      root.style.setProperty('--color-moca-bolt', primary)
      root.style.setProperty('--color-moca-dark', secondary || primary)
    } else {
      root.style.removeProperty('--color-moca-bolt')
      root.style.removeProperty('--color-moca-dark')
    }
  }, [workspace])
  return null
}

function ProtectedRoute({ children, adminOnly = false, superAdminOnly = false }) {
  const { user, loading, isAdmin, isSuperAdmin, workspace } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen"><div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" /></div>
  if (!user) return <Navigate to="/login" replace />
  // Suspended workspace: show friendly screen instead of the app.
  // Super-admin bypasses the suspension gate so they can still operate the
  // platform and re-activate the account from /admin/workspaces.
  if (!isSuperAdmin && workspace && workspace.active === false) {
    return <SuspendedPage />
  }
  if (superAdminOnly && !isSuperAdmin) return <Navigate to="/" replace />
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <ScrapeProvider>
      <BrandThemeApplier />
      <OfflineBanner />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/invite/:token" element={<InvitePage />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="compare" element={<ComparePage />} />
          {/* trends page removed */}
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="executive-summary" element={<ExecutiveSummaryPage />} />
          <Route path="archive" element={<ArchivePage />} />
          <Route path="settings" element={<ProtectedRoute adminOnly><SettingsPage /></ProtectedRoute>} />
          <Route path="preferences" element={<PreferencesPage />} />
          <Route path="workspace/users" element={<ProtectedRoute adminOnly><WorkspaceUsersPage /></ProtectedRoute>} />
          <Route path="workspace/settings" element={<ProtectedRoute adminOnly><WorkspaceBrandingPage /></ProtectedRoute>} />
          <Route path="admin/workspaces" element={<ProtectedRoute superAdminOnly><WorkspacesAdminPage /></ProtectedRoute>} />
          <Route path="admin/audit" element={<ProtectedRoute superAdminOnly><AuditLogPage /></ProtectedRoute>} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </ScrapeProvider>
  )
}
