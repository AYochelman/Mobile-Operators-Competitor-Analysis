import { useEffect, lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { useFeatureFlags } from './hooks/useFeatureFlags'
import { firstVisibleHome } from './data/navFlags'
import { ScrapeProvider } from './hooks/useScrape'
import { getMvnoColors } from './data/mvnoBrandColors'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
// LandingPage is the public "/" entry for anonymous visitors — eager-import it
// (not lazy) so the marketing page paints without a second chunk round-trip.
import LandingPage from './pages/LandingPage'
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
const UsagePage             = lazy(() => import('./pages/UsagePage'))
const UserActivityPage      = lazy(() => import('./pages/UserActivityPage'))
const PositioningPage       = lazy(() => import('./pages/PositioningPage'))
const AIInsightsPage        = lazy(() => import('./pages/AIInsightsPage'))
const InvitePage            = lazy(() => import('./pages/InvitePage'))
const SuspendedPage         = lazy(() => import('./pages/SuspendedPage'))
const NotFoundPage          = lazy(() => import('./pages/NotFoundPage'))
const SocialPage            = lazy(() => import('./pages/SocialPage'))
const GlobalBannersPage     = lazy(() => import('./pages/GlobalBannersPage'))
const ResetPasswordPage     = lazy(() => import('./pages/ResetPasswordPage'))
// MOCA Guest Connect (hotels vertical) — public guest portal + marketing
// landing (both outside the auth gate) and the super-admin operator console.
const GuestPortalPage       = lazy(() => import('./pages/GuestPortalPage'))
const HotelsLandingPage     = lazy(() => import('./pages/HotelsLandingPage'))
const HotelsAdminPage       = lazy(() => import('./pages/HotelsAdminPage'))
// Public B2C eSIM price-comparison page (free, no auth) — sibling of "/".
const EsimComparePage       = lazy(() => import('./pages/EsimComparePage'))
// Public B2C domestic-plans comparison page (free, no auth) — sibling of "/".
const MobileComparePage     = lazy(() => import('./pages/MobileComparePage'))
const EsimAnalyticsPage     = lazy(() => import('./pages/EsimAnalyticsPage'))
const ProviderDealsPage     = lazy(() => import('./pages/ProviderDealsPage'))

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
  const { user, role, loading, isAdmin, isSuperAdmin, workspace } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen"><div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" /></div>
  if (!user) return <Navigate to="/login" replace />
  // `role` is fetched from the backend AFTER `loading` flips false (see useAuth
  // applyContext). On a hard reload of a gated route, redirecting before the
  // role resolves bounces super_admins to "/". Wait for the role instead.
  if ((adminOnly || superAdminOnly) && role == null) {
    return <div className="flex items-center justify-center h-screen"><div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" /></div>
  }
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

/* "/" gate: public marketing landing for logged-out visitors, the full app
   (Layout + Outlet → dashboard) for authenticated users. Deep routes under "/"
   still require login. Keeps the dashboard at "/" for authed users so all
   existing links/redirects stay valid. */
function AppShell() {
  const { user, loading, isSuperAdmin, workspace } = useAuth()
  const location = useLocation()
  if (loading) {
    // Anonymous visitors (no stored session token) get the public landing page
    // immediately — don't gate the marketing page on the Supabase getSession()
    // round-trip (it was delaying the H1, which is the LCP element). Logged-in
    // users (token present) still see the spinner so landing doesn't flash.
    if (location.pathname === '/' && !localStorage.getItem('auth_token')) return <LandingPage />
    return <div className="flex items-center justify-center h-screen"><div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" /></div>
  }
  if (!user) return location.pathname === '/' ? <LandingPage /> : <Navigate to="/login" replace />
  if (!isSuperAdmin && workspace && workspace.active === false) {
    return <Suspense fallback={<PageFallback />}><SuspendedPage /></Suspense>
  }
  return <Layout />
}

// Home ("/" and "/home") renders the editorial dashboard — unless the workspace
// hides it via the hide_dashboard flag (e.g. a global-only client), in which
// case we redirect to its first visible section instead of showing an orphaned
// page with no nav link back to it.
function HomeRoute() {
  const flags = useFeatureFlags()
  if (flags.hide_dashboard) {
    const target = firstVisibleHome(flags)
    if (target !== '/') return <Navigate to={target} replace />
  }
  return <EditorialDashboardPage />
}

// ── Public B2C eSIM page launch switch ──────────────────────────────────────
// Master switch for the consumer eSIM-compare page.
//   import.meta.env.DEV  → true only on the local dev server (`npm run dev`), so
//                          you can preview progress at localhost:5173/esim-deals.
//   production build      → DEV is false, so /esim-deals returns the SPA 404 and
//                          the esim.* host is inert: a build+deploy never exposes
//                          it publicly.
// LAUNCHED 2026-06-27: the consumer eSIM-compare page is public. `true` exposes
// /esim-deals and the esim.mocaintel.com microsite in production builds too.
// (Was `import.meta.env.DEV` while unpublished — flip back to hide it again.)
const ESIM_B2C_LIVE = true

// Access gate for the consumer eSIM page. Public only once launched / in dev
// (ESIM_B2C_LIVE). While unpublished, super-admins can still open it (via the
// dashboard link) to preview the live consumer experience; everyone else gets
// the 404 page, so it stays hidden from the public.
function EsimGate() {
  const { loading, isSuperAdmin } = useAuth()
  if (ESIM_B2C_LIVE) return <EsimComparePage />
  if (loading) return <PageFallback />
  return isSuperAdmin ? <EsimComparePage /> : <NotFoundPage />
}

// Consumer microsite: on esim.mocaintel.com the whole host serves ONLY the
// public B2C eSIM price-comparison page (no B2B app chrome / auth / providers).
// The page reads ?dest / ?lang from the URL, so esim.mocaintel.com/?dest=… works.
const IS_ESIM_HOST = ESIM_B2C_LIVE && typeof window !== 'undefined' &&
  (window.location.hostname === 'esim.mocaintel.com' || window.location.hostname.startsWith('esim.'))

// ── Public B2C domestic-plans page launch switch (/mobile-deals) ────────────
// Same lifecycle as ESIM_B2C_LIVE above: `import.meta.env.DEV` = super-admin
// preview stage (visible on `npm run dev` + to super-admins in production, 404
// for everyone else). Flip to `true` at public launch — together with the
// Stage-2 ship steps (_redirects, sitemap, DNS; see the mobile-deals plan).
const MOBILE_B2C_LIVE = import.meta.env.DEV

function MobileGate() {
  const { loading, isSuperAdmin } = useAuth()
  if (MOBILE_B2C_LIVE) return <MobileComparePage />
  if (loading) return <PageFallback />
  return isSuperAdmin ? <MobileComparePage /> : <NotFoundPage />
}

// mobile.mocaintel.com serves ONLY the domestic-plans consumer page (mirrors
// the esim.* branch — the two prefixes are mutually exclusive). Inert until
// launch: the flag is off in production builds, so the host branch never fires.
const IS_MOBILE_HOST = MOBILE_B2C_LIVE && typeof window !== 'undefined' &&
  (window.location.hostname === 'mobile.mocaintel.com' || window.location.hostname.startsWith('mobile.'))

export default function App() {
  if (IS_ESIM_HOST) {
    return (
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="*" element={<EsimComparePage />} />
        </Routes>
      </Suspense>
    )
  }
  if (IS_MOBILE_HOST) {
    return (
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="*" element={<MobileComparePage />} />
        </Routes>
      </Suspense>
    )
  }
  return (
    <ScrapeProvider>
      <BrandThemeApplier />
      <OfflineBanner />
      <GlobalSearch />
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/invite/:token" element={<InvitePage />} />
          {/* Guest Connect — public, no auth: guest portal (QR target) + /hotels
              marketing landing. Siblings of "/" so they bypass the AppShell gate. */}
          <Route path="/guest/:slug" element={<GuestPortalPage />} />
          <Route path="/hotels" element={<HotelsLandingPage />} />
          {/* Public B2C eSIM price comparison — free, no auth, sibling of "/".
              EsimGate keeps it unpublished (404) until launch, but lets a
              super-admin preview it via the dashboard link. */}
          <Route path="/esim-deals" element={<EsimGate />} />
          {/* Public B2C domestic-plans comparison — free, no auth, sibling of "/".
              MobileGate keeps it unpublished (404) until launch, but lets a
              super-admin preview the live consumer experience. */}
          <Route path="/mobile-deals" element={<MobileGate />} />
          {/* Short branded bio link. Netlify /_redirects 302s /tt for fresh
              visitors; this client route covers repeat visitors whose PWA
              service worker serves index.html (navigateFallback) before the
              redirect can run. Keep the target in sync with public/_redirects. */}
          <Route path="/tt" element={<Navigate to="/esim-deals?utm_source=tiktok&utm_campaign=tiktok_bio" replace />} />
          <Route path="/" element={<AppShell />}>
            {/* Phase 19 — / is the Editorial Deep dashboard (executive view).
                Plan cards UI lives at /plans (and other tab views at /roaming
                /esim /banners /history). Legacy /?tab=X URLs are redirected
                inside EditorialDashboardPage on mount. */}
            <Route index element={<HomeRoute />} />
            {/* "/" is the static marketing page (Netlify serves dist/landing.html);
                /home is the SPA dashboard home — the post-login + "logged-in hit /"
                redirect target. Same component as the index route. */}
            <Route path="home" element={<HomeRoute />} />
            {/* Phase 9 — clean URLs for tab views; DashboardPage detects pathname */}
            <Route path="plans"     element={<DashboardPage />} />
            <Route path="roaming"   element={<DashboardPage />} />
            <Route path="esim"      element={<DashboardPage />} />
            <Route path="esim-banners" element={<GlobalBannersPage />} />
            <Route path="usa"       element={<DashboardPage />} />
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
            <Route path="usage" element={<ProtectedRoute superAdminOnly><UsagePage /></ProtectedRoute>} />
            <Route path="admin/user-activity" element={<ProtectedRoute superAdminOnly><UserActivityPage /></ProtectedRoute>} />
            <Route path="admin/hotels" element={<ProtectedRoute superAdminOnly><HotelsAdminPage /></ProtectedRoute>} />
            <Route path="admin/esim" element={<ProtectedRoute superAdminOnly><EsimAnalyticsPage /></ProtectedRoute>} />
            <Route path="admin/deals" element={<ProtectedRoute superAdminOnly><ProviderDealsPage /></ProtectedRoute>} />
            <Route path="notifications" element={<Navigate to="/alerts?tab=watchlist" replace />} />
            <Route path="ai-insights" element={<AIInsightsPage />} />
            <Route path="social" element={<SocialPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </ScrapeProvider>
  )
}
