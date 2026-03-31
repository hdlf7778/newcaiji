<!--
  任务列表页（TaskList）

  功能：
    - 统计卡片：待处理 / 处理中 / 今日成功 / 今日失败
    - 筛选：状态、模板类型、关键词；支持 URL query 参数初始化
    - 操作：失败任务可重试，所有任务可查看详情弹窗
    - 立即采集弹窗：手动输入采集源 ID 触发任务
    - 每 30 秒自动刷新列表和统计数据
-->
<template>
  <div>
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">任务管理</h2>
      <a-button type="primary" @click="triggerVisible = true">
        ⚡ 立即采集
      </a-button>
    </div>

    <!-- Stat cards -->
    <a-row :gutter="10" style="margin-bottom:16px;">
      <a-col :flex="1" v-for="card in statCards" :key="card.key">
        <div class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">
            {{ stats[card.key] ?? '—' }}
          </div>
        </div>
      </a-col>
    </a-row>

    <!-- Filter bar -->
    <a-card style="margin-bottom:16px;" :body-style="{ padding: '12px 16px' }">
      <a-space wrap>
        <a-space>
          <span style="font-size:13px;color:#595959;">状态</span>
          <a-select v-model:value="query.status" style="width:130px;" @change="onFilterChange">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="pending">待处理</a-select-option>
            <a-select-option value="processing">处理中</a-select-option>
            <a-select-option value="success">成功</a-select-option>
            <a-select-option value="failed">失败</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">模板</span>
          <a-select v-model:value="query.templateType" style="width:140px;" @change="onFilterChange">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="A">A 静态列表</a-select-option>
            <a-select-option value="B">B iframe</a-select-option>
            <a-select-option value="C">C API接口</a-select-option>
            <a-select-option value="G">G SPA渲染</a-select-option>
            <a-select-option value="I">I 政务云</a-select-option>
          </a-select>
        </a-space>
        <a-input-search
          v-model:value="query.keyword"
          placeholder="搜索采集源名称..."
          style="width:240px;"
          allow-clear
          @search="onSearch"
        />
      </a-space>
    </a-card>

    <!-- Table -->
    <a-card :body-style="{ padding: 0 }">
      <a-table
        :columns="columns"
        :data-source="tableData"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="middle"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'source_name'">
            <router-link :to="`/sources/${record.source_id}`" style="color:#1677ff;">
              {{ sourceInfoMap[record.source_id]?.name || `#${record.source_id}` }}
            </router-link>
          </template>
          <template v-if="column.key === 'column_name'">
            {{ sourceInfoMap[record.source_id]?.column_name || '—' }}
          </template>
          <template v-if="column.key === 'template'">
            <a-tag :color="templateColor(record.template)">
              {{ templateLabel(record.template) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">
              {{ statusLabel(record.status) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'duration_ms'">
            {{ record.duration_ms != null ? (record.duration_ms / 1000).toFixed(1) + 's' : '—' }}
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button
                v-if="record.status === 'failed'"
                type="link"
                size="small"
                danger
                :loading="retryingIds.includes(record.id)"
                @click="onRetry(record)"
              >
                重试
              </a-button>
              <a-button type="link" size="small" @click="onViewDetail(record)">
                查看详情
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- Trigger modal -->
    <a-modal
      v-model:open="triggerVisible"
      title="立即采集"
      @ok="onTrigger"
      :confirm-loading="triggerLoading"
    >
      <a-form layout="vertical" style="margin-top:16px;">
        <a-form-item label="采集源 ID" required>
          <a-input-number
            v-model:value="triggerSourceId"
            :min="1"
            style="width:100%;"
            placeholder="请输入采集源 ID"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Detail modal -->
    <a-modal
      v-model:open="detailVisible"
      title="任务详情"
      :footer="null"
      width="640px"
    >
      <a-descriptions :column="2" bordered size="small" style="margin-top:12px;" v-if="detailRecord">
        <a-descriptions-item label="任务ID">{{ detailRecord.id }}</a-descriptions-item>
        <a-descriptions-item label="采集源">
          <router-link :to="`/sources/${detailRecord.source_id}`" style="color:#1677ff;">
            {{ sourceInfoMap[detailRecord.source_id]?.name || `#${detailRecord.source_id}` }}
          </router-link>
        </a-descriptions-item>
        <a-descriptions-item label="模板">
          <a-tag :color="templateColor(detailRecord.template)">{{ templateLabel(detailRecord.template) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="statusColor(detailRecord.status)">{{ statusLabel(detailRecord.status) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="优先级">{{ detailRecord.priority }}</a-descriptions-item>
        <a-descriptions-item label="耗时">{{ detailRecord.duration_ms != null ? (detailRecord.duration_ms / 1000).toFixed(1) + 's' : '—' }}</a-descriptions-item>
        <a-descriptions-item label="新增文章">{{ detailRecord.articles_new ?? '—' }}</a-descriptions-item>
        <a-descriptions-item label="创建时间" :span="2">{{ detailRecord.created_at }}</a-descriptions-item>
        <a-descriptions-item label="错误信息" :span="2" v-if="detailRecord.error_message">
          <span style="color:#ff4d4f;">{{ detailRecord.error_message }}</span>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { taskApi } from '../../api/task.js'
import request from '../../api/request.js'
import { templateLabel, templateColor, statusLabel, statusColor } from '../../constants/source.js'
import { useSourceInfo } from '../../composables/useSourceInfo.js'

const statCards = [
  { key: 'pending', label: '待处理', color: '#1677ff' },
  { key: 'processing', label: '处理中', color: '#fa8c16' },
  { key: 'today_success', label: '今日成功', color: '#52c41a' },
  { key: 'today_failed', label: '今日失败', color: '#ff4d4f' },
]

const stats = ref({})

const query = reactive({
  status: '',
  templateType: '',
  keyword: '',
  page: 1,
  pageSize: 20,
})

const tableData = ref([])
const loading = ref(false)
const total = ref(0)
const retryingIds = ref([])
const triggerVisible = ref(false)
const triggerLoading = ref(false)
const triggerSourceId = ref(null)
const detailVisible = ref(false)
const detailRecord = ref(null)
let autoRefreshTimer = null

const pagination = computed(() => ({
  current: query.page,
  pageSize: query.pageSize,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t) => `共 ${t} 条`,
}))

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 50 },
  { title: '网站名称', dataIndex: 'source_id', key: 'source_name', width: 150 },
  { title: '栏目名称', dataIndex: 'source_id', key: 'column_name', width: 120 },
  { title: '模板', dataIndex: 'template', key: 'template', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '耗时', dataIndex: 'duration_ms', key: 'duration_ms', width: 70 },
  { title: '新增文章', dataIndex: 'articles_new', key: 'articles_new', width: 70 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 155 },
  { title: '操作', key: 'action', width: 140, fixed: 'right' },
]

const { sourceInfoMap, loadForTable } = useSourceInfo()

async function fetchList() {
  loading.value = true
  try {
    const params = {}
    if (query.status) params.status = query.status
    if (query.templateType) params.templateType = query.templateType
    if (query.keyword) params.keyword = query.keyword
    params.page = query.page
    params.pageSize = query.pageSize
    const res = await taskApi.list(params)
    const page = res || {}
    tableData.value = page.records || (Array.isArray(page) ? page : [])
    total.value = page.total || 0
    loadForTable(tableData.value)
  } catch {
    // error handled globally
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await request.get('/api/tasks/stats')
    stats.value = res || {}
  } catch {
    // ignore
  }
}

function onFilterChange() {
  query.page = 1
  fetchList()
}

function onSearch() {
  query.page = 1
  fetchList()
}

function onTableChange(pag) {
  query.page = pag.current
  query.pageSize = pag.pageSize
  fetchList()
}

async function onRetry(record) {
  retryingIds.value = [...retryingIds.value, record.id]
  try {
    await taskApi.retry(record.id)
    message.success('重试请求已提交')
    fetchList()
  } catch {
    // handled globally
  } finally {
    retryingIds.value = retryingIds.value.filter((id) => id !== record.id)
  }
}

function onViewDetail(record) {
  detailRecord.value = record
  detailVisible.value = true
}

async function onTrigger() {
  if (!triggerSourceId.value) {
    message.warning('请输入采集源 ID')
    return
  }
  triggerLoading.value = true
  try {
    await taskApi.create({ sourceId: triggerSourceId.value })
    message.success('采集任务已触发')
    triggerVisible.value = false
    triggerSourceId.value = null
    fetchList()
    fetchStats()
  } catch {
    // handled globally
  } finally {
    triggerLoading.value = false
  }
}

onMounted(() => {
  const routeQuery = useRoute().query
  if (routeQuery.status) query.status = routeQuery.status
  fetchList()
  fetchStats()
  autoRefreshTimer = setInterval(() => {
    fetchList()
    fetchStats()
  }, 30000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})
</script>

<style scoped>
.stat-card {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
  min-width: 0;
}
.stat-label {
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}
</style>
