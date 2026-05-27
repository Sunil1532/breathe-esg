import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401 && !err.config._retry) {
      err.config._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post('/api/auth/refresh/', { refresh })
          localStorage.setItem('access_token', data.access)
          err.config.headers.Authorization = `Bearer ${data.access}`
          return api(err.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      } else {
        localStorage.clear()
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export const login = (username, password) =>
  api.post('/auth/login/', { username, password })

export const getMe = () => api.get('/auth/me/')

export const getDashboard = () => api.get('/dashboard/summary/')

export const getRecords = (params) => api.get('/records/', { params })
export const getRecord = (id) => api.get(`/records/${id}/`)
export const approveRecord = (id, notes) => api.post(`/records/${id}/approve/`, { notes })
export const rejectRecord = (id, notes) => api.post(`/records/${id}/reject/`, { notes })
export const editRecord = (id, data) => api.patch(`/records/${id}/`, data)
export const bulkApprove = (ids) => api.post('/records/bulk-approve/', { ids })
export const bulkReject = (ids, notes) => api.post('/records/bulk-reject/', { ids, notes })
export const getAuditLog = (id) => api.get(`/records/${id}/audit_log/`)

export const ingestFile = (source, file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/ingest/${source}/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getJobs = (source) =>
  api.get('/ingest/jobs/', { params: source ? { source_type: source } : {} })

export default api
