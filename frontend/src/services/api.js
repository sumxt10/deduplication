const request = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(body.detail || `Request failed with status ${response.status}`)
  }
  return body
}

export const api = {
  health: () => request('/health/ready'),
  summary: () => request('/api/v1/dashboard/summary'),
  metrics: () => request('/api/v1/metrics'),
  rawPrometheus: () => fetch('/metrics').then((r) => r.text()),
  events: (params = '') => request(`/api/v1/events${params}`),
  ingest: (event) => request('/api/v1/events', { method: 'POST', body: JSON.stringify(event) }),
  ingestBatch: (events) =>
    request('/api/v1/events/batch', { method: 'POST', body: JSON.stringify({ events }) }),
  replay: (eventId) => request(`/api/v1/events/${eventId}/replay`, { method: 'POST' }),
  reset: () => request('/api/v1/demo/reset', { method: 'POST' }),

  // DLQ management
  dlq: (params = '') => request(`/api/v1/dlq${params}`),
  redriveDlq: (dlqId) => request(`/api/v1/dlq/${dlqId}/redrive`, { method: 'POST' }),
  redriveAllDlq: () => request('/api/v1/dlq/redrive-all', { method: 'POST' }),
  deleteDlq: (dlqId) => request(`/api/v1/dlq/${dlqId}`, { method: 'DELETE' }),

  // CDC Pipeline simulation
  simulateCdc: (config) =>
    request('/api/v1/cdc/simulate', { method: 'POST', body: JSON.stringify(config) }),
  cdcStatus: () => request('/api/v1/cdc/status'),

  // Benchmarking and Jobs
  createJob: (config) => request('/api/v1/jobs', { method: 'POST', body: JSON.stringify(config) }),
  job: (id) => request(`/api/v1/jobs/${id}`),
  jobs: () => request('/api/v1/jobs'),
}