const API_BASE = import.meta.env.VITE_API_URL || ''
const API_KEY = import.meta.env.VITE_API_KEY || ''

async function fetchApi(path, options = {}) {
  const url = `${API_BASE}${path}`
  const headers = { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true', ...options.headers }

  // Add auth token if available
  const token = localStorage.getItem('auth_token')
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(url, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'שגיאת שרת' }))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Plans
  getPlans: (params) => fetchApi(`/api/plans${params ? '?' + new URLSearchParams(params) : ''}`),
  getChanges: (limit = 100) => fetchApi(`/api/changes?limit=${limit}`),
  getAbroadPlans: () => fetchApi('/api/abroad-plans'),
  getAbroadChanges: () => fetchApi('/api/abroad-changes'),
  getGlobalPlans: () => fetchApi('/api/global-plans'),
  getGlobalChanges: () => fetchApi('/api/global-changes'),
  getContentPlans: () => fetchApi('/api/content-plans'),
  getContentChanges: () => fetchApi('/api/content-changes'),

  // Scrape (requires API key)
  scrapeAll: () => fetchApi('/api/scrape-all-now', {
    headers: { 'X-API-Key': API_KEY }
  }),

  // Users (admin)
  getUsers: () => fetchApi('/api/users', {
    headers: { 'X-API-Key': API_KEY }
  }),
  createUser: (data) => fetchApi('/api/users', {
    method: 'POST', body: JSON.stringify(data),
    headers: { 'X-API-Key': API_KEY }
  }),
  deleteUser: (id) => fetchApi(`/api/users/${id}`, {
    method: 'DELETE',
    headers: { 'X-API-Key': API_KEY }
  }),
  updateUserRole: (id, role) => fetchApi(`/api/users/${id}/role`, {
    method: 'POST', body: JSON.stringify({ role }),
    headers: { 'X-API-Key': API_KEY }
  }),

  // Chat
  chat: (question) => fetchApi('/api/chat', { method: 'POST', body: JSON.stringify({ question }), headers: { 'X-API-Key': API_KEY } }),

  // Alerts
  getAlerts: (email) => fetchApi(`/api/alerts?user_email=${encodeURIComponent(email)}`, { headers: { 'X-API-Key': API_KEY } }),
  createAlert: (alert) => fetchApi('/api/alerts', { method: 'POST', body: JSON.stringify(alert), headers: { 'X-API-Key': API_KEY } }),
  deleteAlert: (id) => fetchApi(`/api/alerts/${id}`, { method: 'DELETE', headers: { 'X-API-Key': API_KEY } }),

  // Push
  getVapidKey: () => fetchApi('/api/push/vapid-public-key'),
  subscribe: (sub) => fetchApi('/api/push/subscribe', { method: 'POST', body: JSON.stringify(sub) }),
  unsubscribe: (sub) => fetchApi('/api/push/unsubscribe', { method: 'DELETE', body: JSON.stringify(sub) }),
}
