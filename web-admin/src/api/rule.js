import request from './request.js'

export const ruleApi = {
  list: (params) => request.get('/api/rules', { params }),
  detail: (id) => request.get(`/api/rules/${id}`),
  create: (data) => request.post('/api/rules', data),
  update: (id, data) => request.put(`/api/rules/${id}`, data),
  delete: (id) => request.delete(`/api/rules/${id}`),
  enable: (id) => request.post(`/api/rules/${id}/enable`),
  disable: (id) => request.post(`/api/rules/${id}/disable`),
}
