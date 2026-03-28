/**
 * 任务 API 模块
 *
 * 包含采集任务的 CRUD 操作及死信队列管理接口。
 * 注意：死信的批量操作同时提供了逐条（retryDeadLetter）和批量（batchRetryDeadLetters）两种方式，
 * 页面侧应优先使用批量接口以减少请求数。
 */
import request from './request.js'

export const taskApi = {
  // ── 采集任务 ──
  list: (params) => request.get('/api/tasks', { params }),
  detail: (id) => request.get(`/api/tasks/${id}`),
  create: (data) => request.post('/api/tasks', data),
  cancel: (id) => request.post(`/api/tasks/${id}/cancel`),
  retry: (id) => request.post(`/api/tasks/${id}/retry`),

  // ── 死信队列 ──
  deadLetters: (params) => request.get('/api/dead-letters', { params }),
  retryDeadLetter: (id) => request.post(`/api/dead-letters/${id}/retry`),
  ignoreDeadLetter: (id) => request.post(`/api/dead-letters/${id}/ignore`),
  batchRetryDeadLetters: (ids) => request.post('/api/dead-letters/batch-retry', { ids }),
  batchIgnoreDeadLetters: (ids) => request.post('/api/dead-letters/batch-ignore', { ids }),
}
