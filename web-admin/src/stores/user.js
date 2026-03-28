/**
 * 用户状态管理（Pinia Store）
 *
 * 持久化策略：登录态存储在 localStorage，页面刷新后自动恢复。
 * 注意：logout 仅清除本地状态，未调用后端登出接口。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '../api/request.js'

export const useUserStore = defineStore('user', () => {
  // 从 localStorage 恢复登录态
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')
  const role = ref(localStorage.getItem('role') || '')

  const isLoggedIn = computed(() => !!token.value)

  /** 登录：调用后端接口，成功后同步写入响应式状态和 localStorage */
  async function login(loginUsername, password) {
    const data = await request.post('/api/auth/login', { username: loginUsername, password })
    token.value = data.token
    username.value = data.username
    role.value = data.role
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', data.username)
    localStorage.setItem('role', data.role)
  }

  /** 登出：仅清除本地状态（未调用后端 /logout） */
  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, isLoggedIn, login, logout }
})
