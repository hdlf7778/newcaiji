import request from './request.js'

export const articleApi = {
  list: (params) => request.get('/api/articles', { params }),
  detail: (id) => request.get(`/api/articles/${id}`),
  delete: (id) => request.delete(`/api/articles/${id}`),
  batchDelete: (ids) => request.post('/api/articles/batch-delete', { ids }),
  export: (params) => request.get('/api/articles/export', { params, responseType: 'blob' }),
}
