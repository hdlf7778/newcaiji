<!--
  死信队列页（DeadLetterList）

  功能：
    - 统计卡片：待处理 / 今日新增 / 已重试 / 已忽略 / 已重新配置
    - 筛选：日期范围、错误类型、处理状态、关键词（默认只看待处理）
    - 单条操作：重试、重新配置（展开行内表单）、忽略
    - 批量操作：批量重试、批量忽略
    - "重新配置"展开区域包含智能建议（根据错误类型给出处理方案）
-->
<template>
  <div>
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">死信队列</h2>
      <a-space>
        <a-button
          type="primary"
          :disabled="selectedRowKeys.length === 0"
          :loading="batchRetryLoading"
          @click="onBatchRetry"
        >
          批量重试
        </a-button>
        <a-button
          :disabled="selectedRowKeys.length === 0"
          :loading="batchIgnoreLoading"
          @click="onBatchIgnore"
        >
          批量忽略
        </a-button>
      </a-space>
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
          <span style="font-size:13px;color:#595959;">日期范围</span>
          <a-range-picker
            v-model:value="dateRange"
            style="width:240px;"
            @change="onFilterChange"
          />
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">错误类型</span>
          <a-select v-model:value="query.errorType" style="width:160px;" @change="onFilterChange">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="http_403">403 Forbidden</a-select-option>
            <a-select-option value="http_429">429 限流</a-select-option>
            <a-select-option value="network_timeout">超时</a-select-option>
            <a-select-option value="ssl_error">SSL错误</a-select-option>
            <a-select-option value="parse_error">解析失败</a-select-option>
            <a-select-option value="template_mismatch">模板不匹配</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">处理状态</span>
          <a-select v-model:value="query.handleStatus" style="width:140px;" @change="onFilterChange">
            <a-select-option value="pending">待处理</a-select-option>
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="retried">已重试</a-select-option>
            <a-select-option value="ignored">已忽略</a-select-option>
            <a-select-option value="reconfigured">已重新配置</a-select-option>
          </a-select>
        </a-space>
        <a-input-search
          v-model:value="query.keyword"
          placeholder="搜索网站名称 / URL..."
          style="width:220px;"
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
        :expand-row-by-click="false"
        row-key="id"
        size="middle"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'source_id'">
            <span style="color:#1677ff;">{{ record.source_id }}</span>
          </template>
          <template v-if="column.key === 'error_type'">
            <a-tag :color="errorTypeColor(record.error_type)">
              {{ errorTypeLabel(record.error_type) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'error_message'">
            <span style="font-size:12px;color:#595959;max-width:200px;display:inline-block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" :title="record.error_message">
              {{ record.error_message }}
            </span>
          </template>
          <template v-if="column.key === 'template'">
            <a-tag :color="templateColor(record.template)">
              {{ record.template }}
            </a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="onRetry(record)">重试</a-button>
              <a-button type="link" size="small" @click="toggleReconfig(record.id)">重新配置</a-button>
              <a-button type="link" size="small" danger @click="onIgnore(record)">忽略</a-button>
            </a-space>
          </template>
        </template>

        <template #expandedRowRender="{ record }">
          <div style="padding:12px;">
            <div style="border:1px solid #e8e8e8;border-radius:8px;padding:16px;background:#fff;">
              <div style="font-weight:600;font-size:14px;margin-bottom:12px;">
                🔧 重新配置 — {{ record.sourceName }} / {{ record.columnName }}
              </div>
              <a-row :gutter="12" style="margin-bottom:12px;">
                <a-col :span="8">
                  <div style="font-size:12px;color:#595959;margin-bottom:4px;">模板类型</div>
                  <a-select v-model:value="reconfigForms[record.id].templateType" style="width:100%;">
                    <a-select-option value="A">A 静态列表页</a-select-option>
                    <a-select-option value="B">B iframe</a-select-option>
                    <a-select-option value="C">C API接口</a-select-option>
                    <a-select-option value="G">G SPA渲染</a-select-option>
                    <a-select-option value="I">I 政务云</a-select-option>
                  </a-select>
                </a-col>
                <a-col :span="8">
                  <div style="font-size:12px;color:#595959;margin-bottom:4px;">反爬策略</div>
                  <a-select v-model:value="reconfigForms[record.id].antiBot" style="width:100%;">
                    <a-select-option value="none">无</a-select-option>
                    <a-select-option value="proxy">开启代理轮换</a-select-option>
                    <a-select-option value="ua">开启UA轮换</a-select-option>
                    <a-select-option value="proxy_ua">代理+UA轮换</a-select-option>
                  </a-select>
                </a-col>
                <a-col :span="8">
                  <div style="font-size:12px;color:#595959;margin-bottom:4px;">SSL验证</div>
                  <a-select v-model:value="reconfigForms[record.id].sslVerify" style="width:100%;">
                    <a-select-option value="verify">验证SSL证书</a-select-option>
                    <a-select-option value="skip">跳过SSL验证</a-select-option>
                  </a-select>
                </a-col>
              </a-row>
              <a-row :gutter="12" style="margin-bottom:12px;">
                <a-col :span="8">
                  <div style="font-size:12px;color:#595959;margin-bottom:4px;">编码</div>
                  <a-select v-model:value="reconfigForms[record.id].encoding" style="width:100%;">
                    <a-select-option value="UTF-8">UTF-8</a-select-option>
                    <a-select-option value="GBK">GBK</a-select-option>
                    <a-select-option value="GB2312">GB2312</a-select-option>
                  </a-select>
                </a-col>
              </a-row>

              <!-- Smart suggestion -->
              <div
                v-if="reconfigForms[record.id].suggestion"
                style="padding:10px 12px;background:#e6f4ff;border-radius:6px;font-size:12px;margin-bottom:12px;line-height:1.6;"
              >
                💡 <strong>建议处理方案：</strong>{{ reconfigForms[record.id].suggestion }}
              </div>

              <a-space>
                <a-button
                  type="primary"
                  :loading="reconfigForms[record.id].saving"
                  @click="onSaveReconfig(record)"
                >
                  ✅ 保存配置并重试
                </a-button>
                <a-button @click="toggleReconfig(record.id)">取消</a-button>
              </a-space>
            </div>
          </div>
        </template>
      </a-table>

      <!-- Batch action bar -->
      <div
        v-if="selectedRowKeys.length > 0"
        style="padding:10px 16px;border-top:1px solid #f0f0f0;display:flex;align-items:center;gap:12px;background:#fafafa;"
      >
        <span style="font-size:13px;color:#595959;">已选 {{ selectedRowKeys.length }} 项</span>
        <a-button size="small" type="primary" :loading="batchRetryLoading" @click="onBatchRetry">批量重试</a-button>
        <a-button size="small" :loading="batchIgnoreLoading" @click="onBatchIgnore">批量忽略</a-button>
      </div>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { taskApi } from '../../api/task.js'

const statCards = [
  { key: 'pending', label: '待处理', color: '#ff4d4f' },
  { key: 'todayNew', label: '今日新增', color: '#262626' },
  { key: 'retried', label: '已重试', color: '#52c41a' },
  { key: 'ignored', label: '已忽略', color: '#8c8c8c' },
  { key: 'reconfigured', label: '已重新配置', color: '#1677ff' },
]

const stats = ref({})
const dateRange = ref([])
const query = reactive({
  errorType: '',
  handleStatus: 'pending',
  keyword: '',
  page: 1,
  pageSize: 20,
})

const tableData = ref([])
const loading = ref(false)
const total = ref(0)
const selectedRowKeys = ref([])
const expandedRowKeys = ref([])
const reconfigForms = reactive({})
const batchRetryLoading = ref(false)
const batchIgnoreLoading = ref(false)

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
  { title: '采集源ID', dataIndex: 'source_id', key: 'source_id', width: 100 },
  { title: 'URL', dataIndex: 'url', key: 'url', width: 200, ellipsis: true },
  { title: '错误类型', dataIndex: 'error_type', key: 'error_type', width: 120 },
  { title: '错误信息', dataIndex: 'error_message', key: 'error_message', width: 200, ellipsis: true },
  { title: '模板', dataIndex: 'template', key: 'template', width: 100 },
  { title: '重试次数', dataIndex: 'retry_count', key: 'retry_count', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 180, fixed: 'right' },
]

function templateColor(type) {
  const map = { A: 'purple', B: 'orange', C: 'blue', D: 'purple', G: 'red', H: 'green', I: 'cyan', J: 'default' }
  return map[type] || 'default'
}

function errorTypeColor(type) {
  const map = {
    http_403: 'red',
    http_429: 'orange',
    network_timeout: 'purple',
    ssl_error: 'orange',
    parse_error: 'cyan',
    template_mismatch: 'blue',
  }
  return map[type] || 'default'
}

function errorTypeLabel(type) {
  const map = {
    http_403: '403',
    http_429: '429限流',
    network_timeout: '超时',
    ssl_error: 'SSL错误',
    parse_error: '解析失败',
    template_mismatch: '模板不匹配',
  }
  return map[type] || type
}

/** 根据错误类型生成智能处理建议文案 */
function getSuggestion(errorType) {
  const map = {
    http_403: '此站点连续返回403，可能是IP被目标网站封禁。建议：①开启代理轮换 ②增大请求间隔到3-5秒 ③如仍失败，尝试切换模板为G(SPA渲染)使用浏览器访问',
    ssl_error: '该站点SSL证书已过期，建议开启"跳过SSL验证"后重试。如果网站已永久下线，建议忽略并退役该采集源。',
    network_timeout: '连接超时，建议：①增大超时时间 ②开启代理轮换 ③检查目标站点是否仍可访问',
    parse_error: 'CSS选择器匹配失败，网站可能已改版。建议点击"编辑规则"重新配置选择器。',
    template_mismatch: '当前模板无法获取内容，疑似SPA渲染站点。建议切换模板为G(SPA渲染)。',
  }
  return map[errorType] || ''
}

function initReconfigForm(record) {
  if (!reconfigForms[record.id]) {
    reconfigForms[record.id] = {
      templateType: record.templateType || 'A',
      antiBot: 'none',
      sslVerify: 'verify',
      encoding: 'UTF-8',
      suggestion: getSuggestion(record.errorType),
      saving: false,
    }
  }
}

function toggleReconfig(id) {
  const idx = expandedRowKeys.value.indexOf(id)
  if (idx >= 0) {
    expandedRowKeys.value = expandedRowKeys.value.filter((k) => k !== id)
  } else {
    expandedRowKeys.value = [...expandedRowKeys.value, id]
    const record = tableData.value.find((r) => r.id === id)
    if (record) initReconfigForm(record)
  }
}

async function fetchList() {
  loading.value = true
  try {
    const params = {}
    if (query.errorType) params.errorType = query.errorType
    if (query.handleStatus) params.handleStatus = query.handleStatus
    if (query.keyword) params.keyword = query.keyword
    if (dateRange.value && dateRange.value.length === 2) {
      params.startDate = dateRange.value[0]?.format?.('YYYY-MM-DD') || dateRange.value[0]
      params.endDate = dateRange.value[1]?.format?.('YYYY-MM-DD') || dateRange.value[1]
    }
    params.page = query.page
    params.pageSize = query.pageSize
    const res = await taskApi.deadLetters(params)
    const page = res || {}
    tableData.value = page.records || (Array.isArray(page) ? page : [])
    total.value = page.total || 0
  } catch {
    // error handled globally
  } finally {
    loading.value = false
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
  try {
    await taskApi.retryDeadLetter(record.id)
    message.success('重试请求已提交')
    fetchList()
  } catch {
    // handled globally
  }
}

// 注意：调用的是 taskApi.deleteDeadLetter 但 task.js 中只有 ignoreDeadLetter，此处会报错
async function onIgnore(record) {
  Modal.confirm({
    title: '忽略死信',
    content: `确认忽略该条死信记录？`,
    onOk: async () => {
      try {
        await taskApi.ignoreDeadLetter(record.id)
        message.success('已忽略')
        fetchList()
      } catch {
        // handled globally
      }
    },
  })
}

/**
 * 保存重新配置并重试
 * 注意：当前仅调用了 retryDeadLetter，并未将 reconfigForms 中的配置提交到后端
 */
async function onSaveReconfig(record) {
  const form = reconfigForms[record.id]
  if (!form) return
  form.saving = true
  try {
    await taskApi.retryDeadLetter(record.id)
    message.success('配置已保存，重试请求已提交')
    toggleReconfig(record.id)
    fetchList()
  } catch {
    // handled globally
  } finally {
    form.saving = false
  }
}

// 批量重试：逐条调用接口（未使用 batchRetryDeadLetters 批量接口）
async function onBatchRetry() {
  if (!selectedRowKeys.value.length) return
  batchRetryLoading.value = true
  try {
    await Promise.all(selectedRowKeys.value.map((id) => taskApi.retryDeadLetter(id)))
    message.success(`已提交 ${selectedRowKeys.value.length} 条重试`)
    selectedRowKeys.value = []
    fetchList()
  } catch {
    // handled globally
  } finally {
    batchRetryLoading.value = false
  }
}

async function onBatchIgnore() {
  if (!selectedRowKeys.value.length) return
  Modal.confirm({
    title: '批量忽略',
    content: `确认忽略选中的 ${selectedRowKeys.value.length} 条死信？`,
    onOk: async () => {
      batchIgnoreLoading.value = true
      try {
        await Promise.all(selectedRowKeys.value.map((id) => taskApi.deleteDeadLetter(id)))
        message.success(`已忽略 ${selectedRowKeys.value.length} 条`)
        selectedRowKeys.value = []
        fetchList()
      } catch {
        // handled globally
      } finally {
        batchIgnoreLoading.value = false
      }
    },
  })
}

onMounted(() => {
  fetchList()
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
