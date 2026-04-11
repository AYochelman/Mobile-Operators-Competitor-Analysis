const API_BASE = import.meta.env.VITE_API_URL || ''

async function fetchApi(path, options = {}) {
  const url = `${API_BASE}${path}`
  const headers = { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true', ...options.headers }

  // JWT sent automatically — no API key in frontend
  const token = localStorage.getItem('auth_token')
  if (token) headers['Authorization'] = `Bearer ${token}`

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

  // Scrape — admin only, triggers via JWT auth
  scrapeAll: () => fetchApi('/api/scrape-all-now'),

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

  // Push — JWT auth
  getVapidKey: () => fetchApi('/api/push/vapid-public-key'),
  subscribe:   (sub) => fetchApi('/api/push/subscribe', { method: 'POST', body: JSON.stringify(sub) }),
  unsubscribe: (sub) => fetchApi('/api/push/unsubscribe', { method: 'DELETE', body: JSON.stringify(sub) }),

  // Auth session cookie
  setSessionCookie:  (access_token) => fetchApi('/api/auth/session', { method: 'POST', body: JSON.stringify({ access_token }) }),
  clearSessionCookie:() => fetchApi('/api/auth/logout', { method: 'POST' }),
}
