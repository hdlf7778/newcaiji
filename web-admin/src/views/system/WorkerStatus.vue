<template>
  <div class="worker-status">
    <div class="page-header">
      <h2 class="page-title">
        Worker 状态
        <span class="sub-title">每30秒自动刷新</span>
      </h2>
      <div class="refresh-info">
        下次刷新: {{ countdown }}s
        <a-button size="small" style="margin-left: 8px;" @click="doRefresh">立即刷新</a-button>
      </div>
    </div>

    <a-card :body-style="{ padding: 0 }">
      <a-table
        :columns="columns"
        :data-source="workers"
        :loading="loading"
        :pagination="false"
        row-key="worker_id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <!-- Worker ID -->
          <template v-if="column.key === 'worker_id'">
            <code>{{ record.worker_id }}</code>
          </template>

          <!-- Type -->
          <template v-else-if="column.key === 'worker_type'">
            <a-tag :color="record.worker_type === 'browser' ? 'orange' : 'blue'">
              {{ record.worker_type === 'browser' ? 'Browser' : 'HTTP' }}
            </a-tag>
          </template>

          <!-- Status -->
          <template v-else-if="column.key === 'status'">
            <span class="status-dot" :class="getStatusClass(record)"></span>
            <a-tag :color="getStatusColor(record)">
              {{ getStatusLabel(record) }}
            </a-tag>
          </template>

          <!-- Current task -->
          <template v-else-if="column.key === 'current_task'">
            <code v-if="record.current_task" style="font-size: 12px;">
              {{ record.current_task.substring(0, 8) }}...{{ record.current_task.slice(-4) }}
            </code>
            <span v-else style="color: #bbb;">—</span>
          </template>

          <!-- CPU -->
          <template v-else-if="column.key === 'cpu_percent'">
            <a-progress
              :percent="record.cpu_percent || 0"
              :stroke-color="getCpuColor(record.cpu_percent)"
              size="small"
              :show-info="false"
              style="width: 60px; display: inline-block; vertical-align: middle;"
            />
            <span style="margin-left: 4px; font-size: 12px;">{{ record.cpu_percent }}%</span>
          </template>

          <!-- Memory -->
          <template v-else-if="column.key === 'memory_mb'">
            {{ formatMemory(record.memory_mb) }}
          </template>

          <!-- Last heartbeat -->
          <template v-else-if="column.key === 'last_heartbeat'">
            <span :class="{ 'text-warning': isHeartbeatOld(record.last_heartbeat) }">
              {{ formatHeartbeat(record.last_heartbeat) }}
            </span>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { monitorApi } from '../../api/monitor.js'

const loading = ref(false)
const workers = ref([])
const countdown = ref(30)

let refreshTimer = null
let countdownTimer = null

const columns = [
  { title: 'Worker ID', key: 'worker_id', dataIndex: 'worker_id' },
  { title: '类型', key: 'worker_type', dataIndex: 'worker_type', width: 90 },
  { title: '状态', key: 'status', dataIndex: 'status', width: 110 },
  { title: '当前任务', key: 'current_task', dataIndex: 'current_task' },
  { title: 'CPU%', key: 'cpu_percent', dataIndex: 'cpu_percent', width: 130 },
  { title: '内存', key: 'memory_mb', dataIndex: 'memory_mb', width: 90 },
  { title: '已完成', key: 'completed', dataIndex: 'completed', width: 80 },
  { title: '已失败', key: 'failed', dataIndex: 'failed', width: 80 },
  { title: '运行时长', key: 'uptime', dataIndex: 'uptime', width: 100 },
  { title: '最后心跳', key: 'last_heartbeat', dataIndex: 'last_heartbeat', width: 100 },
]

function isHeartbeatOld(ts) {
  if (!ts) return true
  const seconds = (Date.now() - new Date(ts).getTime()) / 1000
  return seconds > 60
}

function isOffline(record) {
  return isHeartbeatOld(record.last_heartbeat)
}

function getStatusClass(record) {
  if (isOffline(record)) return 'status-offline'
  if (record.status === 'running') return 'status-running'
  if (record.status === 'stopping') return 'status-stopping'
  return 'status-idle'
}

function getStatusColor(record) {
  if (isOffline(record)) return 'default'
  if (record.status === 'running') return 'green'
  if (record.status === 'stopping') return 'red'
  return 'blue'
}

function getStatusLabel(record) {
  if (isOffline(record)) return '离线'
  if (record.status === 'running') return '运行中'
  if (record.status === 'stopping') return '停止中'
  return '空闲'
}

function getCpuColor(pct) {
  if (!pct) return '#52c41a'
  if (pct > 80) return '#ff4d4f'
  if (pct > 60) return '#fa8c16'
  return '#52c41a'
}

function formatMemory(mb) {
  if (!mb) return '—'
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${mb} MB`
}

function formatHeartbeat(ts) {
  if (!ts) return '未知'
  const seconds = Math.floor((Date.now() - new Date(ts).getTime()) / 1000)
  if (seconds < 60) return `${seconds}秒前`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`
  return `${Math.floor(seconds / 3600)}小时前`
}

async function doRefresh() {
  loading.value = true
  try {
    const res = await monitorApi.workers()
    workers.value = Array.isArray(res) ? res : (res?.records || [])
  } catch (e) {
    message.error('获取Worker状态失败')
  } finally {
    loading.value = false
    countdown.value = 30
  }
}

onMounted(() => {
  doRefresh()
  refreshTimer = setInterval(doRefresh, 30000)
  countdownTimer = setInterval(() => {
    countdown.value = Math.max(0, countdown.value - 1)
  }, 1000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>

<style scoped>
.worker-status {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.sub-title {
  font-size: 12px;
  font-weight: 400;
  color: #888;
  margin-left: 8px;
}

.refresh-info {
  font-size: 13px;
  color: #666;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.status-running {
  background: #52c41a;
  box-shadow: 0 0 0 2px #52c41a40;
  animation: pulse 1.5s infinite;
}

.status-idle {
  background: #1677ff;
}

.status-stopping {
  background: #ff4d4f;
}

.status-offline {
  background: #bbb;
}

.text-warning {
  color: #fa8c16;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 2px #52c41a40; }
  50% { box-shadow: 0 0 0 4px #52c41a30; }
}
</style>
