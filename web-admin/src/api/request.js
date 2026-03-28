/**
 * 全局 Axios 请求封装
 *
 * 职责：
 *   1. 请求拦截：自动附加 Bearer Token
 *   2. 响应拦截：解包后端 Result<T> 信封格式（{success, data, message}），
 *      成功时直接返回 data，失败时弹出错误提示并 reject
 *   3. 401 处理：清除本地登录态并跳转登录页
 */
import axios from 'axios'
import { message } from 'ant-design-vue'

const request = axios.create({
  baseURL: '',
  timeout: 15000,
})

// ── 请求拦截器：注入 JWT Token ──
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── 响应拦截器：解包 Result<T> + 全局错误处理 ──
request.interceptors.response.use(
  (response) => {
    const body = response.data
    // 后端返回 {success, data, code} 格式时，自动解包
    // 页面侧直接拿到 data（如 {records, total}），无需再 .data
    if (body && typeof body === 'object' && 'success' in body) {
      if (!body.success) {
        const msg = body.message || '请求失败'
        message.error(msg)
        return Promise.reject(new Error(msg))
      }
      return body.data !== undefined ? body.data : body
    }
    // 非信封格式（如文件下载等），原样返回
    return body
  },
  (error) => {
    // 401 未授权：清除登录态并强制跳转
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      localStorage.removeItem('role')
      window.location.href = '/login'
      return Promise.reject(error)
    }
    const msg = error.response?.data?.message || error.message || '请求失败'
    message.error(msg)
    return Promise.reject(error)
  }
)

export default request
