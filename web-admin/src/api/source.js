import request from './request.js'

export const sourceApi = {
  list: (params) => request.get('/api/sources', { params }),
  detail: (id) => request.get(`/api/sources/${id}`),
  create: (data) => request.post('/api/sources', data),
  update: (id, data) => request.put(`/api/sources/${id}`, data),
  delete: (id) => request.delete(`/api/sources/${id}`),
  import: (formData) => request.post('/api/sources/import', formData),
  approve: (id, operator) => request.post(`/api/sources/${id}/approve`, null, { params: { operator } }),
  reject: (id) => request.post(`/api/sources/${id}/reject`),
  batchApprove: (sourceIds, operator) => request.post('/api/sources/batch-approve', { sourceIds, operator }),
  pause: (id) => request.post(`/api/sources/${id}/pause`),
  resume: (id) => request.post(`/api/sources/${id}/resume`),
  detect: (id) => request.post(`/api/sources/${id}/detect`),
  statsByStatus: () => request.get('/api/sources/stats-by-status'),
  statistics: () => request.get('/api/sources/statistics'),
  reviewList: (params) => request.get('/api/sources/review-list', { params }),
}
