import request from './request.js'

export const monitorApi = {
  dashboard: () => request.get('/api/monitor/dashboard'),
  workers: () => request.get('/api/monitor/workers'),
  workerDetail: (id) => request.get(`/api/monitor/workers/${id}`),
  metrics: (params) => request.get('/api/monitor/metrics', { params }),
}
