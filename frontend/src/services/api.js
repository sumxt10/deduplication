const request = async (path, options = {}) => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`)
  return body
}
export const api = {
  summary: () => request('/api/v1/dashboard/summary'),
  metrics: () => request('/api/v1/metrics'),
  events: (params = '') => request(`/api/v1/events${params}`),
  dlq: () => request('/api/v1/dlq'),
  health: () => request('/health/ready'),
  ingest: (event) => request('/api/v1/events', { method: 'POST', body: JSON.stringify(event) }),
  reset: () => request('/api/v1/demo/reset', { method: 'POST' }),
  createJob: (config) => request('/api/v1/jobs', { method: 'POST', body: JSON.stringify(config) }),
  job: (id) => request(`/api/v1/jobs/${id}`),
}