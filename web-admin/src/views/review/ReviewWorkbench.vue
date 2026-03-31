<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">审核工作台</h2>
      <div style="font-size:13px;color:#666;display:flex;align-items:center;gap:8px;">
        <span>快捷键: <kbd style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:11px;border:1px solid #ddd;">Y</kbd>=通过
        <kbd style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:11px;border:1px solid #ddd;">N</kbd>=跳过
        <kbd style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:11px;border:1px solid #ddd;">R</kbd>=拒绝</span>
      </div>
    </div>

    <!-- 统计卡片 + 筛选 -->
    <a-card :body-style="{ padding: '12px 16px' }" style="margin-bottom:16px;">
      <a-space wrap size="middle">
        <span style="font-size:13px;color:#595959;">评分筛选</span>
        <a-select v-model:value="scoreFilter" style="width:180px;" @change="fetchList">
          <a-select-option value="">全部试采结果</a-select-option>
          <a-select-option value="high">≥ 0.8（高质量）</a-select-option>
          <a-select-option value="medium">0.6 - 0.8（需审核）</a-select-option>
          <a-select-option value="low">< 0.6（需排查）</a-select-option>
        </a-select>
        <a-divider type="vertical" />
        <span style="font-size:13px;">
          共 <strong style="color:#1677ff;">{{ total }}</strong> 条
          &nbsp;|&nbsp; 已选 <strong style="color:#fa8c16;">{{ selectedRowKeys.length }}</strong> 条
        </span>
        <a-button
          type="primary"
          :disabled="selectedRowKeys.length === 0"
          :loading="batchLoading"
          @click="onBatchApprove"
        >
          批量上线 ({{ selectedRowKeys.length }})
        </a-button>
        <a-button
          danger
          :disabled="selectedRowKeys.length === 0"
          @click="onBatchReject"
        >
          批量拒绝
        </a-button>
      </a-space>
    </a-card>

    <!-- 列表 -->
    <a-card :body-style="{ padding: 0 }">
      <a-table
        :columns="columns"
        :data-source="tableData"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
        row-key="id"
        size="middle"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <router-link :to="`/sources/${record.id}`" style="color:#1677ff;">
              {{ record.name }}
            </router-link>
          </template>
          <template v-if="column.key === 'trial_score'">
            <a-tag :color="scoreColor(record.trial_score)">
              {{ record.trial_score != null ? record.trial_score : '—' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">
              {{ statusLabel(record.status) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'template'">
            <a-tag>{{ templateLabel(record.template) }}</a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" style="color:#52c41a;" @click="onApprove(record)">通过</a-button>
              <a-button type="link" size="small" @click="$router.push(`/sources/${record.id}`)">详情</a-button>
              <a-button type="link" size="small" danger @click="onReject(record)">拒绝</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { sourceApi } from '../../api/source.js'
import request from '../../api/request.js'
import { templateLabel, statusLabel, statusColor, scoreColor } from '../../constants/source.js'
import { useUserStore } from '../../stores/user.js'

const userStore = useUserStore()

const loading = ref(false)
const batchLoading = ref(false)
const tableData = ref([])
const total = ref(0)
const scoreFilter = ref('')
const selectedRowKeys = ref([])
const page = ref(1)
const pageSize = ref(20)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '网站名称', dataIndex: 'name', key: 'name', width: 180 },
  { title: '栏目名称', dataIndex: 'column_name', key: 'column_name', width: 130 },
  { title: '试采评分', dataIndex: 'trial_score', key: 'trial_score', width: 100, sorter: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '模板', dataIndex: 'template', key: 'template', width: 110 },
  { title: '地区', dataIndex: 'region', key: 'region', width: 120 },
  { title: '操作', key: 'action', width: 160, fixed: 'right' },
]

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t) => `共 ${t} 条`,
}))

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys) => { selectedRowKeys.value = keys },
}))

async function fetchList() {
  loading.value = true
  try {
    // 查询所有试采完成的源（TRIAL_PASSED + TRIAL_FAILED + PENDING_REVIEW）
    const statuses = 'TRIAL_PASSED,TRIAL_FAILED,PENDING_REVIEW'
    const res = await request.get('/api/sources/review-all', {
      params: { statuses, scoreFilter: scoreFilter.value, page: page.value, pageSize: pageSize.value }
    })
    const pg = res || {}
    tableData.value = pg.records || (Array.isArray(pg) ? pg : [])
    total.value = pg.total || 0
  } catch {
    // fallback: 用普通列表接口
    try {
      const params = { page: page.value, pageSize: pageSize.value }
      // 根据筛选条件设置 status
      if (scoreFilter.value === 'low') {
        params.status = 'TRIAL_FAILED'
      } else {
        params.status = 'TRIAL_PASSED'
      }
      const res = await sourceApi.list(params)
      const pg = res || {}
      tableData.value = pg.records || []
      total.value = pg.total || 0
    } catch { /* ignore */ }
  } finally {
    loading.value = false
  }
}

function onTableChange(pag) {
  page.value = pag.current
  pageSize.value = pag.pageSize
  fetchList()
}

async function onApprove(record) {
  try {
    await sourceApi.approve(record.id, userStore.username)
    message.success(`${record.name} 已上线`)
    fetchList()
  } catch { /* handled */ }
}

async function onReject(record) {
  try {
    await sourceApi.reject(record.id)
    message.warning(`${record.name} 已拒绝`)
    fetchList()
  } catch { /* handled */ }
}

async function onBatchApprove() {
  if (!selectedRowKeys.value.length) return
  batchLoading.value = true
  try {
    await sourceApi.batchApprove(selectedRowKeys.value, userStore.username)
    message.success(`${selectedRowKeys.value.length} 个采集源已批量上线`)
    selectedRowKeys.value = []
    fetchList()
  } catch {
    message.error('批量操作失败')
  } finally {
    batchLoading.value = false
  }
}

async function onBatchReject() {
  if (!selectedRowKeys.value.length) return
  try {
    await Promise.all(selectedRowKeys.value.map(id => sourceApi.reject(id)))
    message.warning(`${selectedRowKeys.value.length} 个采集源已拒绝`)
    selectedRowKeys.value = []
    fetchList()
  } catch {
    message.error('批量操作失败')
  }
}

// 键盘快捷键
function handleKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  if (!tableData.value.length) return
}

onMounted(() => {
  fetchList()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>
