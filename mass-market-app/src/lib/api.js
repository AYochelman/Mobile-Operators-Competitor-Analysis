const API_BASE = import.meta.env.VITE_API_URL || ''

async function fetchApi(path, options = {}) {
  const url = `${API_BASE}${path}`
  const headers = { 'Content-Type': 'application/json', ...options.headers }

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

  // Scrape
  scrapeAll: () => fetchApi('/api/scrape-all-now'),

  // Chat
  chat: (question) => fetchApi('/api/chat', { method: 'POST', body: JSON.stringify({ question }) }),

  // Push
  getVapidKey: () => fetchApi('/api/push/vapid-public-key'),
  subscribe: (sub) => fetchApi('/api/push/subscribe', { method: 'POST', body: JSON.stringify(sub) }),
  unsubscribe: (sub) => fetchApi('/api/push/unsubscribe', { method: 'DELETE', body: JSON.stringify(sub) }),
}
