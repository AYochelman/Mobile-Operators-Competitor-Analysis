export const API_BASE = import.meta.env.VITE_API_URL || ''
const DEV_API_KEY = import.meta.env.VITE_DEV_API_KEY || ''

async function fetchApi(path, options = {}) {
  const url = `${API_BASE}${path}`
  const headers = { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true', ...options.headers }

  const token = localStorage.getItem('auth_token')
  if (token) headers['Authorization'] = `Bearer ${token}`
  // Dev-only API key (only present in .env, never in .env.production)
  if (DEV_API_KEY) headers['X-API-Key'] = DEV_API_KEY

  const res = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',  // sends httpOnly auth_token cookie on every request
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'שגיאת שרת' }))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Plans (public — rate limited server-side)
  getPlans:        (params) => fetchApi(`/api/plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getChanges:      (limit = 100) => fetchApi(`/api/changes?limit=${limit}`),
  getAbroadPlans:  () => fetchApi('/api/abroad-plans'),
  getAbroadChanges:() => fetchApi('/api/abroad-changes'),
  getGlobalPlans:  () => fetchApi('/api/global-plans'),
  getGlobalChanges:() => fetchApi('/api/global-changes'),
  getContentPlans: () => fetchApi('/api/content-plans'),
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
  scrapeAll: () => fetchApi('/api/scrape-all-now'),
  getRefreshQuota: () => fetchApi('/api/refresh-quota'),

  // Users — admin only, JWT auth
  getUsers:       () => fetchApi('/api/users'),
  createUser:     (data) => fetchApi('/api/users', { method: 'POST', body: JSON.stringify(data) }),
  deleteUser:     (id) => fetchApi(`/api/users/${id}`, { method: 'DELETE' }),
  updateUserRole: (id, role) => fetchApi(`/api/users/${id}/role`, { method: 'POST', body: JSON.stringify({ role }) }),

  // Chat — JWT auth
  chat: (question) => fetchApi('/api/chat', { method: 'POST', body: JSON.stringify({ question }) }),

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

  // Audit log — super_admin only
  getAuditLog: (queryString = '') => fetchApi(`/api/audit-log${queryString}`),

  // Invite links
  createInvite:  (workspaceId, role) => fetchApi(`/api/workspaces/${workspaceId}/invite`, { method: 'POST', body: JSON.stringify({ role }) }),
  getInvite:     (token) => fetchApi(`/api/invite/${token}`),
  acceptInvite:  (token) => fetchApi(`/api/invite/${token}/accept`, { method: 'POST' }),
}
