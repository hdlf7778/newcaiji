<!--
  采集源列表页（SourceList）

  功能：
    - 状态卡片筛选：点击状态卡片切换筛选条件
    - 多维筛选：模板类型、平台、地区、健康度、关键词
    - 批量操作：审批、暂停、退役
    - 支持从 URL query 参数读取初始 status（仪表盘点击跳转场景）
-->
<template>
  <div>
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">采集源管理</h2>
      <a-space>
        <router-link to="/sources/create">
          <a-button type="primary">
            <template #icon><PlusOutlined /></template>
            新增采集源
          </a-button>
        </router-link>
        <router-link to="/sources/import">
          <a-button>
            <template #icon><UploadOutlined /></template>
            批量导入
          </a-button>
        </router-link>
        <a-button>
          <template #icon><BankOutlined /></template>
          平台导入
        </a-button>
      </a-space>
    </div>

    <!-- Stat cards -->
    <a-row :gutter="10" style="margin-bottom:16px;">
      <a-col v-for="card in statCards" :key="card.key" :flex="1">
        <div
          class="stat-card"
          :class="{ 'stat-card-active': query.status === card.key }"
          @click="onStatusCardClick(card.key)"
        >
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">
            {{ statCounts[card.key] ?? '—' }}
          </div>
        </div>
      </a-col>
    </a-row>

    <!-- Filter bar -->
    <a-card style="margin-bottom:16px;" :body-style="{ padding: '12px 16px' }">
      <a-space wrap>
        <a-space>
          <span style="font-size:13px;color:#595959;">模板</span>
          <a-select v-model:value="query.templateType" style="width:140px;" @change="fetchList">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="A">A 静态列表</a-select-option>
            <a-select-option value="B">B iframe</a-select-option>
            <a-select-option value="C">C API接口</a-select-option>
            <a-select-option value="D">D 微信</a-select-option>
            <a-select-option value="G">G SPA渲染</a-select-option>
            <a-select-option value="H">H 混合</a-select-option>
            <a-select-option value="I">I 政务云</a-select-option>
            <a-select-option value="J">J 其他</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">平台</span>
          <a-select v-model:value="query.platform" style="width:140px;" @change="fetchList">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="JPAAS">JPAAS</a-select-option>
            <a-select-option value="dfwsrc">dfwsrc</a-select-option>
            <a-select-option value="WordPress">WordPress</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">地区</span>
          <a-select v-model:value="query.region" style="width:140px;" @change="fetchList">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="浙江">浙江</a-select-option>
            <a-select-option value="黑龙江">黑龙江</a-select-option>
            <a-select-option value="福建">福建</a-select-option>
            <a-select-option value="湖南">湖南</a-select-option>
            <a-select-option value="广东">广东</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">健康</span>
          <a-select v-model:value="query.healthRange" style="width:130px;" @change="fetchList">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="0-49">0-49 差</a-select-option>
            <a-select-option value="50-69">50-69 中</a-select-option>
            <a-select-option value="70-89">70-89 良</a-select-option>
            <a-select-option value="90-100">90-100 优</a-select-option>
          </a-select>
        </a-space>
        <a-input-search
          v-model:value="query.keyword"
          placeholder="搜索网站名称 / 栏目 / URL..."
          style="width:280px;"
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
          <template v-if="column.key === 'templateType'">
            <a-tag :color="templateColor(record.template)">
              {{ templateLabel(record.template) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">
              {{ statusLabel(record.status) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'health'">
            <div style="display:flex;align-items:center;gap:6px;">
              <span
                style="display:inline-block;width:8px;height:8px;border-radius:50%;"
                :style="{ background: healthDotColor(record.health_score) }"
              />
              {{ record.health_score }}
            </div>
          </template>
          <template v-if="column.key === 'action'">
            <router-link :to="`/sources/${record.id}`">
              <a-button type="link" size="small">详情</a-button>
            </router-link>
          </template>
        </template>
      </a-table>

      <!-- Batch action bar -->
      <div
        v-if="selectedRowKeys.length > 0"
        style="padding:10px 16px;border-top:1px solid #f0f0f0;display:flex;align-items:center;gap:12px;background:#fafafa;"
      >
        <span style="font-size:13px;color:#595959;">已选 {{ selectedRowKeys.length }} 项</span>
        <a-button size="small" type="primary" @click="onBatchApprove">批量审批</a-button>
        <a-button size="small" @click="onBatchPause">批量暂停</a-button>
        <a-button size="small" danger @click="onBatchRetire">批量退役</a-button>
      </div>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, UploadOutlined, BankOutlined } from '@ant-design/icons-vue'
import { sourceApi } from '../../api/source.js'

const route = useRoute()

const statCards = [
  { key: '', label: '全部', color: '#262626' },
  { key: 'active', label: '🟢 活跃', color: '#52c41a' },
  { key: 'pending_detect', label: '⏳ 待检测', color: '#595959' },
  { key: 'pending_review', label: '📋 待审核', color: '#fa8c16' },
  { key: 'error', label: '🔴 异常', color: '#ff4d4f' },
  { key: 'paused', label: '⏸️ 暂停', color: '#8c8c8c' },
  { key: 'retired', label: '🗑️ 退役', color: '#8c8c8c' },
]

const statCounts = ref({})

const query = reactive({
  status: '',
  templateType: '',
  platform: '',
  region: '',
  healthRange: '',
  keyword: '',
  page: 1,
  pageSize: 20,
})

const tableData = ref([])
const loading = ref(false)
const total = ref(0)
const selectedRowKeys = ref([])

const pagination = computed(() => ({
  current: query.page,
  pageSize: query.pageSize,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t) => `共 ${t} 条`,
}))

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys) => { selectedRowKeys.value = keys },
}))

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '网站名称', dataIndex: 'name', key: 'name', width: 180 },
  { title: '栏目名称', dataIndex: 'column_name', key: 'column_name', width: 140 },
  { title: '模板', dataIndex: 'template', key: 'templateType', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '健康', dataIndex: 'health_score', key: 'health', width: 90 },
  { title: '地区', dataIndex: 'region', key: 'region', width: 120 },
  { title: '静默天数', dataIndex: 'quiet_days', key: 'quiet_days', width: 90 },
  { title: '最后采集', dataIndex: 'last_success_at', key: 'last_success_at', width: 130 },
  { title: '操作', key: 'action', width: 80, fixed: 'right' },
]

// 模板类型枚举 → 显示信息映射
const TEMPLATE_LABELS = {
  STATIC_LIST: { letter: 'A', label: '静态列表', color: 'purple' },
  IFRAME_LOADER: { letter: 'B', label: 'iframe加载', color: 'orange' },
  API_JSON: { letter: 'C', label: 'API接口', color: 'blue' },
  WECHAT_ARTICLE: { letter: 'D', label: '微信公众号', color: 'green' },
  SEARCH_DISCOVERY: { letter: 'E', label: '搜索监控', color: 'cyan' },
  AUTH_REQUIRED: { letter: 'F', label: '登录态', color: 'red' },
  SPA_RENDER: { letter: 'G', label: 'SPA渲染', color: 'volcano' },
  RSS_FEED: { letter: 'H', label: 'RSS订阅', color: 'lime' },
  GOV_CLOUD_PLATFORM: { letter: 'I', label: '政务云', color: 'geekblue' },
  CAPTURED_API: { letter: 'J', label: '抓包API', color: 'default' },
}

function templateLabel(type) {
  const t = TEMPLATE_LABELS[type]
  return t ? `${t.letter} ${t.label}` : type
}

function templateColor(type) {
  return TEMPLATE_LABELS[type]?.color || 'default'
}

// 采集源状态枚举 → 标签文案和颜色
const STATUS_MAP = {
  PENDING_DETECT: { label: '待检测', color: 'default' },
  DETECTING:      { label: '检测中', color: 'processing' },
  DETECTED:       { label: '检测完成', color: 'cyan' },
  DETECT_FAILED:  { label: '检测失败', color: 'error' },
  TRIAL:          { label: '试采中', color: 'processing' },
  TRIAL_PASSED:   { label: '试采通过', color: 'cyan' },
  TRIAL_FAILED:   { label: '试采失败', color: 'error' },
  PENDING_REVIEW: { label: '待审核', color: 'warning' },
  APPROVED:       { label: '已审批', color: 'blue' },
  ACTIVE:         { label: '活跃', color: 'success' },
  PAUSED:         { label: '暂停', color: 'default' },
  ERROR:          { label: '异常', color: 'error' },
  RETIRED:        { label: '退役', color: 'default' },
}

function statusColor(status) {
  return STATUS_MAP[status]?.color || 'default'
}

function statusLabel(status) {
  return STATUS_MAP[status]?.label || status
}

/** 根据健康分数返回颜色：>=90 绿 / >=70 蓝 / >=50 橙 / <50 红 */
function healthDotColor(score) {
  if (score >= 90) return '#52c41a'
  if (score >= 70) return '#1677ff'
  if (score >= 50) return '#fa8c16'
  return '#ff4d4f'
}

async function fetchList() {
  loading.value = true
  try {
    const params = {}
    if (query.status) params.status = query.status
    if (query.templateType) params.templateType = query.templateType
    if (query.platform) params.platform = query.platform
    if (query.region) params.region = query.region
    if (query.healthRange) params.healthRange = query.healthRange
    if (query.keyword) params.keyword = query.keyword
    params.page = query.page
    params.pageSize = query.pageSize
    const res = await sourceApi.list(params)
    const page = res || {}
    tableData.value = page.records || (Array.isArray(page) ? page : [])
    total.value = page.total || 0
  } catch {
    // error handled globally
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await sourceApi.statsByStatus()
    statCounts.value = res || {}
  } catch {
    // ignore
  }
}

function onStatusCardClick(key) {
  query.status = key
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

async function onBatchApprove() {
  if (!selectedRowKeys.value.length) return
  Modal.confirm({
    title: '批量审批',
    content: `确认审批选中的 ${selectedRowKeys.value.length} 个采集源？`,
    onOk: async () => {
      try {
        await sourceApi.batchApprove(selectedRowKeys.value, 'admin')
        message.success('批量审批成功')
        selectedRowKeys.value = []
        fetchList()
        fetchStats()
      } catch {
        // handled globally
      }
    },
  })
}

// 批量暂停：逐条调用 pause 接口（无批量接口，存在 N+1 请求问题）
async function onBatchPause() {
  if (!selectedRowKeys.value.length) return
  Modal.confirm({
    title: '批量暂停',
    content: `确认暂停选中的 ${selectedRowKeys.value.length} 个采集源？`,
    onOk: async () => {
      try {
        await Promise.all(selectedRowKeys.value.map((id) => sourceApi.pause(id)))
        message.success('批量暂停成功')
        selectedRowKeys.value = []
        fetchList()
        fetchStats()
      } catch {
        // handled globally
      }
    },
  })
}

// 批量退役：逐条调用 delete 接口（同上，N+1 请求问题）
async function onBatchRetire() {
  if (!selectedRowKeys.value.length) return
  Modal.confirm({
    title: '批量退役',
    content: `确认退役选中的 ${selectedRowKeys.value.length} 个采集源？此操作不可撤销。`,
    okType: 'danger',
    onOk: async () => {
      try {
        await Promise.all(selectedRowKeys.value.map((id) => sourceApi.delete(id)))
        message.success('批量退役成功')
        selectedRowKeys.value = []
        fetchList()
        fetchStats()
      } catch {
        // handled globally
      }
    },
  })
}

onMounted(() => {
  // 从 URL 参数读取筛选条件（如从仪表盘点击跳转）
  if (route.query.status) {
    query.status = route.query.status
  }
  fetchList()
  fetchStats()
})
</script>

<style scoped>
.stat-card {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
  min-width: 0;
}
.stat-card:hover {
  border-color: #1677ff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.1);
}
.stat-card-active {
  border-color: #1677ff;
  background: #e6f4ff;
}
.stat-label {
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 4px;
  white-space: nowrap;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}
</style>
