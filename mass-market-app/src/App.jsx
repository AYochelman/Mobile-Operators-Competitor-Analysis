import { useEffect, lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { ScrapeProvider } from './hooks/useScrape'
import { getMvnoColors } from './data/mvnoBrandColors'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import OfflineBanner from './components/OfflineBanner'
import GlobalSearch from './components/GlobalSearch'
import Spinner from './components/ui/Spinner'

// Lazy-loaded pages (split into separate chunks)
// DashboardPage is the heaviest single page (1500+ lines, pulls in PlanCard,
// BannerMosaic, CompetitorBoard, HistoryTab, NewsTab, charts, modals, ...).
// Splitting it out shrinks the initial bundle for users who land elsewhere
// (bookmarks, /alerts, /archive, etc.) and doesn't hurt the dashboard
// itself — Suspense's PageFallback already wraps the route tree.
const EditorialDashboardPage = lazy(() => import('./pages/EditorialDashboardPage'))
const DashboardPage         = lazy(() => import('./pages/DashboardPage'))
const ComparePage           = lazy(() => import('./pages/ComparePage'))
const AlertsPage            = lazy(() => import('./pages/AlertsPage'))
const ExecutiveSummaryPage  = lazy(() => import('./pages/ExecutiveSummaryPage'))
const ArchivePage           = lazy(() => import('./pages/ArchivePage'))
const SettingsPage          = lazy(() => import('./pages/SettingsPage'))
const PreferencesPage       = lazy(() => import('./pages/PreferencesPage'))
const WorkspacesAdminPage   = lazy(() => import('./pages/WorkspacesAdminPage'))
const WorkspaceUsersPage    = lazy(() => import('./pages/WorkspaceUsersPage'))
const WorkspaceBrandingPage = lazy(() => import('./pages/WorkspaceBrandingPage'))
const AuditLogPage          = lazy(() => import('./pages/AuditLogPage'))
const PositioningPage       = lazy(() => import('./pages/PositioningPage'))
const AIInsightsPage        = lazy(() => import('./pages/AIInsightsPage'))
const InvitePage            = lazy(() => import('./pages/InvitePage'))
const SuspendedPage         = lazy(() => import('./pages/SuspendedPage'))
const NotFoundPage          = lazy(() => import('./pages/NotFoundPage'))

function PageFallback() {
  return <div className="flex justify-center py-20"><Spinner /></div>
}

function BrandThemeApplier() {
  const { workspace } = useAuth()
  useEffect(() => {
    const root = document.documentElement
    const cfg = workspace?.brand_config || {}
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
  if (!isSuperAdmin && workspace && workspace.active === false) {
    return (
      <Suspense fallback={<PageFallback />}>
        <SuspendedPage />
      </Suspense>
    )
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
      <GlobalSearch />
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/invite/:token" element={<InvitePage />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            {/* Phase 19 — / is the Editorial Deep dashboard (executive view).
                Plan cards UI lives at /plans (and other tab views at /roaming
                /esim /banners /history). Legacy /?tab=X URLs are redirected
                inside EditorialDashboardPage on mount. */}
            <Route index element={<EditorialDashboardPage />} />
            {/* Phase 9 — clean URLs for tab views; DashboardPage detects pathname */}
            <Route path="plans"     element={<DashboardPage />} />
            <Route path="roaming"   element={<DashboardPage />} />
            <Route path="esim"      element={<DashboardPage />} />
            <Route path="resellers" element={<DashboardPage />} />
            <Route path="content"   element={<DashboardPage />} />
            <Route path="news"      element={<DashboardPage />} />
            <Route path="banners"  element={<DashboardPage />} />
            <Route path="history"  element={<DashboardPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="positioning" element={<PositioningPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="executive-summary" element={<ExecutiveSummaryPage />} />
            <Route path="archive" element={<ArchivePage />} />
            <Route path="settings" element={<ProtectedRoute adminOnly><SettingsPage /></ProtectedRoute>} />
            <Route path="preferences" element={<PreferencesPage />} />
            <Route path="workspace/users" element={<ProtectedRoute adminOnly><WorkspaceUsersPage /></ProtectedRoute>} />
            <Route path="workspace/settings" element={<ProtectedRoute adminOnly><WorkspaceBrandingPage /></ProtectedRoute>} />
            <Route path="admin/workspaces" element={<ProtectedRoute superAdminOnly><WorkspacesAdminPage /></ProtectedRoute>} />
            <Route path="admin/audit" element={<ProtectedRoute superAdminOnly><AuditLogPage /></ProtectedRoute>} />
            <Route path="notifications" element={<Navigate to="/alerts?tab=watchlist" replace />} />
            <Route path="ai-insights" element={<AIInsightsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </ScrapeProvider>
  )
}
