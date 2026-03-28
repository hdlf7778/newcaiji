<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <DatabaseOutlined class="login-logo-icon" />
        <h2 class="login-title">源画像库</h2>
        <p class="login-subtitle">采集系统管理平台</p>
      </div>

      <a-form :model="form" layout="vertical" @finish="handleLogin">
        <a-form-item name="username" :rules="[{ required: true, message: '请输入用户名' }]">
          <a-input
            v-model:value="form.username"
            size="large"
            placeholder="用户名"
            :prefix="h(UserOutlined)"
          />
        </a-form-item>

        <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password
            v-model:value="form.password"
            size="large"
            placeholder="密码"
            :prefix="h(LockOutlined)"
          />
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            block
            :loading="loading"
          >
            登 录
          </a-button>
        </a-form-item>
      </a-form>
    </div>
  </div>
</template>

<script setup>
import { h, ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { DatabaseOutlined, UserOutlined, LockOutlined } from '@ant-design/icons-vue'
import { useUserStore } from '../stores/user.js'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function handleLogin() {
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    message.success('登录成功')
    router.push('/dashboard')
  } catch {
    // error message handled by request interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background-color: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  background: #fff;
  border-radius: 8px;
  padding: 40px;
  width: 380px;
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.08);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo-icon {
  font-size: 48px;
  color: #1677ff;
}

.login-title {
  margin: 12px 0 4px;
  font-size: 24px;
  font-weight: 700;
  color: #262626;
}

.login-subtitle {
  margin: 0;
  color: #8c8c8c;
  font-size: 14px;
}
</style>
