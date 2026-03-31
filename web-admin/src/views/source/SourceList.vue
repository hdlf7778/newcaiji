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
          <a-select v-model:value="query.templateType" style="width:150px;" @change="fetchList" allowClear placeholder="全部">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="static_list">A 静态列表</a-select-option>
            <a-select-option value="iframe_loader">B iframe加载</a-select-option>
            <a-select-option value="api_json">C API接口</a-select-option>
            <a-select-option value="wechat_article">D 微信公众号</a-select-option>
            <a-select-option value="search_discovery">E 搜索监控</a-select-option>
            <a-select-option value="auth_required">F 登录态</a-select-option>
            <a-select-option value="spa_render">G SPA渲染</a-select-option>
            <a-select-option value="rss_feed">H RSS订阅</a-select-option>
            <a-select-option value="gov_cloud_platform">I 政务云</a-select-option>
            <a-select-option value="captured_api">J 抓包API</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">评分</span>
          <a-select v-model:value="query.scoreRange" style="width:140px;" @change="fetchList" allowClear placeholder="全部">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="high">≥ 0.8 高质量</a-select-option>
            <a-select-option value="medium">0.6-0.8 需审核</a-select-option>
            <a-select-option value="low">&lt; 0.6 需排查</a-select-option>
            <a-select-option value="none">未试采</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">状态</span>
          <a-select v-model:value="query.status" style="width:130px;" @change="fetchList" allowClear placeholder="全部">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="pending_detect">待检测</a-select-option>
            <a-select-option value="detected">检测完成</a-select-option>
            <a-select-option value="trial_passed">试采通过</a-select-option>
            <a-select-option value="trial_failed">试采失败</a-select-option>
            <a-select-option value="approved">已审批</a-select-option>
            <a-select-option value="active">活跃</a-select-option>
            <a-select-option value="paused">暂停</a-select-option>
            <a-select-option value="error">异常</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">地区</span>
          <a-select v-model:value="query.region" style="width:120px;" @change="fetchList" allowClear placeholder="全部" show-search>
            <a-select-option value="">全部</a-select-option>
            <a-select-option v-for="r in regionOptions" :key="r" :value="r">{{ r }}</a-select-option>
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
          <template v-if="column.key === 'trial_score'">
            <a-tag v-if="record.trial_score != null" :color="record.trial_score >= 0.8 ? 'green' : record.trial_score >= 0.6 ? 'orange' : 'red'">
              {{ record.trial_score }}
            </a-tag>
            <span v-else style="color:#bfbfbf;">—</span>
          </template>
          <template v-if="column.key === 'action'">
            <router-link :to="`/sources/${record.id}`">
              <a-button type="link" size="small">详情</a-button>
            </router-link>
          </template>
        </template>
      </a-table>

    </a-card>

    <!-- Batch action bar — 固定在页面底部 -->
    <div
      v-if="selectedRowKeys.length > 0"
      style="position:fixed;bottom:0;left:220px;right:0;z-index:100;padding:12px 24px;background:#fff;border-top:2px solid #1677ff;box-shadow:0 -2px 8px rgba(0,0,0,0.1);display:flex;align-items:center;gap:12px;flex-wrap:wrap;"
    >
      <span style="font-size:14px;font-weight:600;color:#1677ff;">已选 {{ selectedRowKeys.length }} 项</span>
      <a-button :loading="batchDetectLoading" @click="onBatchDetect">
        🔍 批量检测模板
      </a-button>
      <a-button :loading="batchTrialLoading" @click="onBatchTrial">
        🧪 批量试采
      </a-button>
      <a-button type="primary" @click="onBatchApprove">批量审批上线</a-button>
      <a-button @click="onBatchPause">批量暂停</a-button>
      <a-button danger @click="onBatchRetire">批量退役</a-button>
      <a-button type="link" @click="selectedRowKeys = []">取消选择</a-button>
    </div>
    <div v-if="selectedRowKeys.length > 0" style="height:56px;"></div>

      <!-- Batch progress modal -->
      <a-modal
        v-model:open="batchProgressVisible"
        :title="batchProgressTitle"
        :footer="null"
        :closable="!batchRunning"
        :maskClosable="false"
        width="500px"
      >
        <div style="margin-bottom:12px;">
          <a-progress :percent="batchPercent" :status="batchRunning ? 'active' : 'success'" />
        </div>
        <div style="font-size:13px;color:#595959;margin-bottom:8px;">
          进度: {{ batchDone }}/{{ batchTotal }} | 成功: {{ batchSuccess }} | 失败: {{ batchFail }}
        </div>
        <div style="max-height:200px;overflow:auto;font-size:12px;font-family:monospace;background:#f5f5f5;padding:8px;border-radius:4px;">
          <div v-for="(log, i) in batchLogs.slice(-20)" :key="i" :style="{ color: log.startsWith('✅') ? '#52c41a' : log.startsWith('❌') ? '#ff4d4f' : '#595959' }">
            {{ log }}
          </div>
        </div>
        <div v-if="!batchRunning" style="margin-top:12px;text-align:right;">
          <a-button type="primary" @click="batchProgressVisible = false; fetchList(); fetchStats();">
            完成
          </a-button>
        </div>
      </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { PlusOutlined, UploadOutlined, BankOutlined } from '@ant-design/icons-vue'
import { sourceApi } from '../../api/source.js'
import request from '../../api/request.js'
import { templateLabel, templateColor, statusLabel, statusColor } from '../../constants/source.js'

const route = useRoute()

const statCards = [
  { key: '', label: '全部', color: '#262626' },
  { key: 'active', label: '🟢 活跃', color: '#52c41a' },
  { key: 'pending_detect', label: '⏳ 待检测', color: '#595959' },
  { key: 'trial_passed', label: '✅ 试采通过', color: '#13c2c2' },
  { key: 'trial_failed', label: '❌ 试采失败', color: '#ff4d4f' },
  { key: 'pending_review', label: '📋 待审核', color: '#fa8c16' },
  { key: 'error', label: '🔴 异常', color: '#ff4d4f' },
  { key: 'paused', label: '⏸️ 暂停', color: '#8c8c8c' },
  { key: 'retired', label: '🗑️ 退役', color: '#8c8c8c' },
]

const statCounts = ref({})

const query = reactive({
  status: '',
  templateType: '',
  region: '',
  scoreRange: '',
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

// 全国省份列表
const regionOptions = [
  '北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江',
  '上海','江苏','浙江','安徽','福建','江西','山东',
  '河南','湖北','湖南','广东','广西','海南',
  '重庆','四川','贵州','云南','西藏',
  '陕西','甘肃','青海','宁夏','新疆','国家',
]

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '网站名称', dataIndex: 'name', key: 'name', width: 170 },
  { title: '栏目名称', dataIndex: 'column_name', key: 'column_name', width: 120 },
  { title: '模板', dataIndex: 'template', key: 'templateType', width: 110 },
  { title: '试采评分', dataIndex: 'trial_score', key: 'trial_score', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '地区', dataIndex: 'region', key: 'region', width: 110 },
  { title: '操作', key: 'action', width: 80, fixed: 'right' },
]

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
    if (query.templateType) params.template = query.templateType
    if (query.region) params.region = query.region
    if (query.scoreRange) params.scoreRange = query.scoreRange
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

// ── 批量检测/试采 ──
const batchDetectLoading = ref(false)
const batchTrialLoading = ref(false)
const batchProgressVisible = ref(false)
const batchProgressTitle = ref('')
const batchRunning = ref(false)
const batchTotal = ref(0)
const batchDone = ref(0)
const batchSuccess = ref(0)
const batchFail = ref(0)
const batchLogs = ref([])
const batchPercent = computed(() => batchTotal.value > 0 ? Math.round(batchDone.value / batchTotal.value * 100) : 0)

async function onBatchDetect() {
  if (!selectedRowKeys.value.length) return
  Modal.confirm({
    title: '批量检测模板',
    content: `将对选中的 ${selectedRowKeys.value.length} 个采集源执行模板检测和规则生成，确认继续？`,
    onOk: () => runBatchProcess('detect'),
  })
}

async function onBatchTrial() {
  if (!selectedRowKeys.value.length) return
  Modal.confirm({
    title: '批量试采',
    content: `将对选中的 ${selectedRowKeys.value.length} 个采集源执行试采验证，确认继续？`,
    onOk: () => runBatchProcess('trial'),
  })
}

async function runBatchProcess(type) {
  const ids = [...selectedRowKeys.value]
  batchProgressTitle.value = type === 'detect' ? '批量检测模板' : '批量试采'
  batchTotal.value = ids.length
  batchDone.value = 0
  batchSuccess.value = 0
  batchFail.value = 0
  batchLogs.value = []
  batchRunning.value = true
  batchProgressVisible.value = true

  if (type === 'detect') batchDetectLoading.value = true
  else batchTrialLoading.value = true

  for (const id of ids) {
    const src = tableData.value.find(s => s.id === id)
    const name = src?.name || `#${id}`
    try {
      if (type === 'detect') {
        // 检测：POST /api/sources/{id}/detect
        try {
          await request.post(`/api/sources/${id}/detect`)
          batchSuccess.value++
          batchLogs.value.push(`✅ ${name} — 检测完成`)
        } catch (err) {
          // detect 接口可能返回非 success，也算完成（规则可能为空但模板已识别）
          batchSuccess.value++
          batchLogs.value.push(`⚠️ ${name} — 检测完成（${err.message || '规则可能为空'}）`)
        }
      } else {
        // 试采：POST /api/sources/{id}/trial（执行试采并写入评分）
        try {
          const trialRes = await request.post(`/api/sources/${id}/trial`)
          const score = trialRes?.score ?? 0
          const count = trialRes?.count ?? 0
          if (trialRes?.success && count > 0) {
            batchSuccess.value++
            batchLogs.value.push(`✅ ${name} — ${count}篇 评分${score}`)
          } else {
            batchFail.value++
            batchLogs.value.push(`❌ ${name} — ${trialRes?.error || '匹配0篇'} 评分${score}`)
          }
        } catch (err) {
          batchFail.value++
          batchLogs.value.push(`❌ ${name} — ${err.message || '请求失败'}`)
        }
      }
    } catch (e) {
      batchFail.value++
      batchLogs.value.push(`❌ ${name} — ${e.message || '请求失败'}`)
    }
    batchDone.value++
  }

  batchRunning.value = false
  batchDetectLoading.value = false
  batchTrialLoading.value = false
  selectedRowKeys.value = []
  // 刷新列表
  fetchList()
  fetchStats()
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
