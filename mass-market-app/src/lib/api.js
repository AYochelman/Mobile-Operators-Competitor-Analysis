export const API_BASE = import.meta.env.VITE_API_URL || ''
const DEV_API_KEY = import.meta.env.VITE_DEV_API_KEY || ''

// Deduplicate concurrent GET requests to the same URL.
// If a request is already in-flight, callers share the same Promise instead of
// making duplicate network calls (e.g. DashboardPage + WatchlistProvider both
// calling getChanges on mount).
const _inflight = new Map()

async function fetchApi(path, options = {}) {
  const url = `${API_BASE}${path}`
  const method = (options.method || 'GET').toUpperCase()
  const headers = { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true', ...options.headers }

  const token = localStorage.getItem('auth_token')
  if (token) headers['Authorization'] = `Bearer ${token}`
  // Dev-only API key (only present in .env, never in .env.production)
  if (DEV_API_KEY) headers['X-API-Key'] = DEV_API_KEY

  if (method === 'GET' && _inflight.has(url)) return _inflight.get(url)

  const promise = fetch(url, {
    ...options,
    headers,
    credentials: 'include',  // sends httpOnly auth_token cookie on every request
  })
    .then(async res => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'שגיאת שרת' }))
        throw new Error(err.error || `HTTP ${res.status}`)
      }
      return res.json()
    })
    .finally(() => { _inflight.delete(url) })

  if (method === 'GET') _inflight.set(url, promise)
  return promise
}

export const api = {
  // Plans (public — rate limited server-side)
  getPlans:        (params) => fetchApi(`/api/plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getChanges:      (limit = 100) => fetchApi(`/api/changes?limit=${limit}`),
  getAbroadPlans:  (params) => fetchApi(`/api/abroad-plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getAbroadChanges:() => fetchApi('/api/abroad-changes'),
  getGlobalPlans:  (params) => fetchApi(`/api/global-plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getGlobalChanges:() => fetchApi('/api/global-changes'),
  getResellerPlans: (params) => fetchApi(`/api/reseller-plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getUsaPlans:     (params) => fetchApi(`/api/usa-plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getContentPlans: (params) => fetchApi(`/api/content-plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getContentChanges:() => fetchApi('/api/content-changes'),
  getBanners:      () => fetchApi('/api/banners'),
  getStoreBanners: () => fetchApi('/api/store-banners'),
  getArchive:      (carrier, date) => fetchApi(`/api/archive?carrier=${encodeURIComponent(carrier)}&date=${encodeURIComponent(date)}`),
  getArchiveDateRange: () => fetchApi('/api/archive/date-range'),
  getHistoryChanges: (carrier, planType, fromDate = '', toDate = '') => {
    const p = new URLSearchParams({ carrier, plan_type: planType })
    if (fromDate) p.append('from', fromDate)
    if (toDate)   p.append('to', toDate)
    return fetchApi(`/api/history/changes?${p}`)
  },
  getHistoryPriceSeries: (carrier, planType, planName = '', fromDate = '') => {
    const p = new URLSearchParams({ carrier, plan_type: planType })
    if (planName)  p.append('plan_name', planName)
    if (fromDate)  p.append('from', fromDate)
    return fetchApi(`/api/history/price-series?${p}`)
  },
  analyzeHistory: (carrier, planType, fromDate = '', toDate = '') => {
    const p = new URLSearchParams({ carrier, plan_type: planType })
    if (fromDate) p.append('from', fromDate)
    if (toDate)   p.append('to', toDate)
    return fetchApi(`/api/history/analyze?${p}`)
  },

  // Scrape — admin only, triggers via JWT auth
  scrapeAll:        () => fetchApi('/api/scrape-all-now'),
  scrapeProgress:   () => fetchApi('/api/scrape-progress/state'),
  getRefreshQuota:  () => fetchApi('/api/refresh-quota'),

  // Users — admin only, JWT auth
  getUsers:       () => fetchApi('/api/users'),
  createUser:     (data) => fetchApi('/api/users', { method: 'POST', body: JSON.stringify(data) }),
  deleteUser:     (id) => fetchApi(`/api/users/${id}`, { method: 'DELETE' }),
  updateUserRole: (id, role) => fetchApi(`/api/users/${id}/role`, { method: 'POST', body: JSON.stringify({ role }) }),
  adminSetPassword: (id, password) => fetchApi(`/api/users/${id}/password`, { method: 'POST', body: JSON.stringify({ password }) }),

  // Chat — JWT auth. model: 'sonnet' (default, better Hebrew) | 'haiku' (faster/cheaper)
  chat: (question, model) => fetchApi('/api/chat', {
    method: 'POST',
    body: JSON.stringify(model ? { question, model } : { question }),
  }),

  // Alerts — JWT auth
  getAlerts:   () => fetchApi('/api/alerts'),
  createAlert: (alert) => fetchApi('/api/alerts', { method: 'POST', body: JSON.stringify(alert) }),
  deleteAlert: (id) => fetchApi(`/api/alerts/${id}`, { method: 'DELETE' }),

  // Executive summary
  getExecutiveSummary:     () => fetchApi('/api/executive-summary'),
  refreshExecutiveSummary: () => fetchApi('/api/executive-summary/refresh', { method: 'POST' }),

  // Social sentiment
  getSocialSentiment:     () => fetchApi('/api/social-sentiment'),
  refreshSocialSentiment: () => fetchApi('/api/social-sentiment/refresh', { method: 'POST' }),

  // News
  getNews: (carrier = null) =>
    fetchApi(`/api/news${carrier && carrier !== 'all' ? `?carrier=${encodeURIComponent(carrier)}` : ''}`),

  // Affiliate analytics — admin only
  getAffiliateStats: (days = 30) =>
    fetchApi(`/api/affiliate/stats?days=${days}`),

  // Claude API usage — admin only. days=0 returns lifetime totals.
  getClaudeUsageSummary: (days = 30) =>
    fetchApi(`/api/usage/summary?days=${days}`),
  getClaudeUsageRecent:  (limit = 100) =>
    fetchApi(`/api/usage/recent?limit=${limit}`),
  // Set / clear the budget driving the remaining-balance + depletion estimate.
  // total=null clears it. asOf (YYYY-MM-DD, optional) counts spend from that date.
  setClaudeUsageBudget:  (total, asOf = null) =>
    fetchApi('/api/usage/budget', {
      method: 'POST',
      body: JSON.stringify({ total_usd: total, as_of: asOf }),
    }),
  // Authoritative org-wide spend from Anthropic's Admin Cost API (needs
  // config.json:anthropic_admin_key). Returns spend in USD, not balance.
  getOfficialCost:       (days = 30) =>
    fetchApi(`/api/usage/official-cost?days=${days}`),

  // Notification message language (he|en) — applies to Telegram / WhatsApp /
  // Web Push / Slack + the morning digest. Admin only.
  getNotificationSettings: () => fetchApi('/api/settings/notifications'),
  setNotificationSettings: (notify_lang) =>
    fetchApi('/api/settings/notifications', {
      method: 'POST',
      body: JSON.stringify({ notify_lang }),
    }),

  // Push — JWT auth
  getVapidKey: () => fetchApi('/api/push/vapid-public-key'),
  subscribe:   (sub) => fetchApi('/api/push/subscribe', { method: 'POST', body: JSON.stringify(sub) }),
  unsubscribe: (sub) => fetchApi('/api/push/unsubscribe', { method: 'DELETE', body: JSON.stringify(sub) }),

  // Auth session cookie
  setSessionCookie:  (access_token) => fetchApi('/api/auth/session', { method: 'POST', body: JSON.stringify({ access_token }) }),
  clearSessionCookie:() => fetchApi('/api/auth/logout', { method: 'POST' }),

  // Contact form (suspended users or any authenticated user)
  sendContact: (message) => fetchApi('/api/contact', { method: 'POST', body: JSON.stringify({ message }) }),

  // Workspaces — super_admin only
  getWorkspaces:        () => fetchApi('/api/workspaces'),
  createWorkspace:      (data) => fetchApi('/api/workspaces', { method: 'POST', body: JSON.stringify(data) }),
  updateWorkspace:      (id, data) => fetchApi(`/api/workspaces/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  getWorkspaceUsers:    (id) => fetchApi(`/api/workspaces/${id}/users`),
  assignWorkspaceUser:  (id, email, role) => fetchApi(`/api/workspaces/${id}/users`, { method: 'POST', body: JSON.stringify({ email, role }) }),
  unassignWorkspaceUser:(id, userId) => fetchApi(`/api/workspaces/${id}/users/${userId}`, { method: 'DELETE' }),

  // Workspace branding — workspace admin of own workspace
  updateWorkspaceBranding: (data) => fetchApi('/api/workspace/branding', { method: 'PATCH', body: JSON.stringify(data) }),
  testSlackWebhook: (webhook_url) => fetchApi('/api/workspace/slack-test', { method: 'POST', body: JSON.stringify({ webhook_url }) }),

  // Audit log — super_admin only
  getAuditLog: (queryString = '') => fetchApi(`/api/audit-log${queryString}`),

  // User activity (super_admin operator dashboard).
  // trackActivity bypasses fetchApi: the beacon returns 204 (no JSON body, which
  // fetchApi would choke on) and we want a fire-and-forget POST with keepalive
  // so a page_view survives an immediate navigation/unload.
  trackActivity: (event_type, path = null, details = null) => {
    try {
      const token = localStorage.getItem('auth_token')
      const headers = { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (DEV_API_KEY) headers['X-API-Key'] = DEV_API_KEY
      return fetch(`${API_BASE}/api/activity`, {
        method: 'POST', headers, credentials: 'include', keepalive: true,
        body: JSON.stringify({ event_type, path, details }),
      })
    } catch {
      return Promise.resolve()
    }
  },
  getActivityOverview: (days = 30) => fetchApi(`/api/activity/overview?days=${days}`),
  getActivityEvents: (params = {}) => {
    const p = new URLSearchParams()
    if (params.email)      p.append('email', params.email)
    if (params.event_type) p.append('event_type', params.event_type)
    if (params.days != null)  p.append('days', String(params.days))
    if (params.limit != null) p.append('limit', String(params.limit))
    return fetchApi(`/api/activity/events${p.toString() ? '?' + p : ''}`)
  },

  // Invite links
  createInvite:     (workspaceId, role) => fetchApi(`/api/workspaces/${workspaceId}/invite`, { method: 'POST', body: JSON.stringify({ role }) }),
  createInviteBulk: (workspaceId, emails, role) => fetchApi(`/api/workspaces/${workspaceId}/invite-bulk`, { method: 'POST', body: JSON.stringify({ emails, role }) }),
  getInvite:        (token) => fetchApi(`/api/invite/${token}`),
  acceptInvite:     (token) => fetchApi(`/api/invite/${token}/accept`, { method: 'POST' }),

  // Email digest — super_admin only
  triggerDigest: (workspaceId) => fetchApi(`/api/workspaces/${workspaceId}/trigger-digest`, { method: 'POST' }),

  // Saved views — per-user filter presets
  getSavedViews:    () => fetchApi('/api/saved-views'),
  createSavedView:  (name, filters) => fetchApi('/api/saved-views', { method: 'POST', body: JSON.stringify({ name, filters }) }),
  deleteSavedView:  (id) => fetchApi(`/api/saved-views/${id}`, { method: 'DELETE' }),

  // User preferences
  updateMyPreferences: (prefs) => fetchApi('/api/my-preferences', { method: 'PATCH', body: JSON.stringify(prefs) }),

  // Market movers — top biggest % price moves. planTypes: array/string of 'domestic','abroad','global'
  getMarketMovers: (days = 7, limit = 5, planTypes = null) => {
    const qs = new URLSearchParams({ days: String(days), limit: String(limit) })
    if (planTypes && planTypes.length) {
      qs.set('plan_types', Array.isArray(planTypes) ? planTypes.join(',') : planTypes)
    }
    return fetchApi(`/api/market-movers?${qs.toString()}`)
  },

  // Health / status — super_admin operational info
  getHealth: () => fetchApi('/api/health'),

  // Watchlist — per-user starred plans
  getWatchlist:    () => fetchApi('/api/watchlist'),
  addToWatchlist:  (plan) => fetchApi('/api/watchlist', { method: 'POST', body: JSON.stringify(plan) }),
  removeFromWatchlist: (plan) => fetchApi('/api/watchlist', {
    method: 'DELETE',
    body: JSON.stringify(plan),
    headers: { 'Content-Type': 'application/json' },
  }),

  // Provider coupons — manually curated discount codes for global eSIM providers
  getCoupons:       () => fetchApi('/api/coupons'),
  getAllCoupons:    () => fetchApi('/api/coupons/all'),
  createCoupon:     (data) => fetchApi('/api/coupons', { method: 'POST', body: JSON.stringify(data) }),
  updateCoupon:     (id, data) => fetchApi(`/api/coupons/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteCoupon:     (id) => fetchApi(`/api/coupons/${id}`, { method: 'DELETE' }),

  // Annotations — workspace-wide team notes on plans
  getAnnotations: (carrier, planName, planType) => {
    const p = new URLSearchParams()
    if (carrier)  p.append('carrier', carrier)
    if (planName) p.append('plan_name', planName)
    if (planType) p.append('plan_type', planType)
    return fetchApi(`/api/annotations${p.toString() ? '?' + p : ''}`)
  },
  getAnnotationCounts: () => fetchApi('/api/annotations/counts'),
  addAnnotation: (data) => fetchApi('/api/annotations', { method: 'POST', body: JSON.stringify(data) }),
  updateAnnotation: (id, note) => fetchApi(`/api/annotations/${id}`, { method: 'PATCH', body: JSON.stringify({ note }) }),
  deleteAnnotation: (id) => fetchApi(`/api/annotations/${id}`, { method: 'DELETE' }),

  // ── MOCA Guest Connect (hotels vertical) ──────────────────────────────────
  // Public guest portal: branding + live Israel deal feed (no auth).
  getGuestPortal: (slug) => fetchApi(`/api/guest/${encodeURIComponent(slug)}`),
  // Anonymous engagement beacon — fire-and-forget (204, no JSON body).
  guestEvent: (slug, event_type, lang = null) => {
    try {
      return fetch(`${API_BASE}/api/guest/${encodeURIComponent(slug)}/event`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' },
        keepalive: true,
        body: JSON.stringify({ event_type, lang }),
      })
    } catch {
      return Promise.resolve()
    }
  },
  // Attribution deep link: routes the click through Flask /go so the hotel earns
  // and the provider page opens. Returns an absolute URL (open in a new tab).
  guestGoUrl: (slug, provider, plan, lang = 'en') => {
    const p = new URLSearchParams({ hotel: slug, plan: plan || '', country: 'Israel', lang })
    return `${API_BASE}/go/${encodeURIComponent(provider)}?${p.toString()}`
  },
  // Branded QR (SVG) for an <img src>; base = the public origin the QR encodes.
  guestQrUrl: (slug, base) => {
    const b = base || (typeof window !== 'undefined' ? window.location.origin : 'https://mocaintel.com')
    return `${API_BASE}/api/guest/${encodeURIComponent(slug)}/qr.svg?base=${encodeURIComponent(b)}`
  },
  // Public lead capture from the /hotels marketing landing.
  submitHotelLead: (data) => fetchApi('/api/hotels/lead', { method: 'POST', body: JSON.stringify(data) }),

  // Operator console — super_admin (or dev API key).
  getHotels:         () => fetchApi('/api/hotels'),
  createHotel:       (data) => fetchApi('/api/hotels', { method: 'POST', body: JSON.stringify(data) }),
  updateHotel:       (slug, data) => fetchApi(`/api/hotels/${encodeURIComponent(slug)}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteHotel:       (slug) => fetchApi(`/api/hotels/${encodeURIComponent(slug)}`, { method: 'DELETE' }),
  getHotelAnalytics: (slug, days = 30) => fetchApi(`/api/hotels/${encodeURIComponent(slug)}/analytics?days=${days}`),
  getHotelLeads:     () => fetchApi('/api/hotels/leads'),
}
