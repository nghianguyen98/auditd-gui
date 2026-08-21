// API client with automatic JWT auth headers

const BASE = '/api'

function getToken() {
  return localStorage.getItem('tv_token')
}

function setToken(token) {
  localStorage.setItem('tv_token', token)
}

function removeToken() {
  localStorage.removeItem('tv_token')
  localStorage.removeItem('tv_user')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const res = await fetch(BASE + path, { ...options, headers })

  if (res.status === 401) {
    removeToken()
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  return res.status === 204 ? null : res.json()
}

export const apiGet = (path) => request(path)
export const apiPost = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) })
export const apiPut = (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body) })
export const apiDelete = (path) => request(path, { method: 'DELETE' })

export const api = {
  // Auth
  login: async (username, password) => {
    const body = new URLSearchParams({ username, password })
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Login failed')
    }
    const data = await res.json()
    setToken(data.access_token)
    localStorage.setItem('tv_user', JSON.stringify({ username: data.username, is_admin: data.is_admin }))
    return data
  },

  logout: () => { removeToken() },

  me: () => request('/auth/me'),

  getUsers: () => request('/auth/users'),
  createUser: (body) => request('/auth/users', { method: 'POST', body: JSON.stringify(body) }),
  deleteUser: (u) => request(`/auth/users/${u}`, { method: 'DELETE' }),
  changePassword: (u, password) => request(`/auth/users/${u}/password`, {
    method: 'POST', body: JSON.stringify({ password })
  }),

  // Dashboard
  stats:        () => request('/dashboard/stats'),
  activityChart:(hours = 24) => request(`/dashboard/activity-chart?hours=${hours}`),
  topUsers:     (days = 7) => request(`/dashboard/top-users?days=${days}`),
  recentAlerts: (limit = 5) => request(`/dashboard/recent-alerts?limit=${limit}`),

  // Sessions
  sessions: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v != null && q.set(k, v))
    return request(`/sessions?${q}`)
  },
  session:  (id) => request(`/sessions/${id}`),
  sessionCommands: (id, params = {}) => {
    const q = new URLSearchParams(params)
    return request(`/sessions/${id}/commands?${q}`)
  },
  sessionFiles: (id) => request(`/sessions/${id}/files`),

  // Alerts
  alerts: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v != null && q.set(k, v))
    return request(`/alerts?${q}`)
  },
  resolveAlert:   (id) => request(`/alerts/${id}/resolve`, { method: 'PATCH' }),
  resolveAllAlerts: ()  => request('/alerts/resolve-all', { method: 'PATCH' }),
  alertSummary:   () => request('/alerts/summary'),

  // Settings
  getSettings:    () => request('/settings'),
  updateSettings: (body) => request('/settings', { method: 'PUT', body: JSON.stringify(body) }),
}

export function getStoredUser() {
  try { return JSON.parse(localStorage.getItem('tv_user') || 'null') }
  catch { return null }
}

export function isAuthenticated() {
  return !!getToken()
}
