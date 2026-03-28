<!--
  采集源详情页（SourceDetail）

  功能：
    - 展示采集源基本信息、运行状态、健康评分
    - 操作按钮：触发采集、重新检测、暂停/恢复、退役
    - 采集规则展示（JSON 格式化）并可跳转到规则编辑页
    - 右侧时间线展示最近操作日志（可展开/收起）
-->
<template>
  <div v-if="detail">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;">
      <div>
        <h2 style="font-size:18px;font-weight:600;margin:0 0 4px;">
          {{ detail.name }} — {{ detail.columnName }}
        </h2>
        <div style="font-size:12px;color:#8c8c8c;">
          ID: {{ detail.id }}
          &nbsp;|&nbsp;
          <a-typography-text copyable style="font-size:12px;color:#1677ff;">
            {{ detail.url }}
          </a-typography-text>
        </div>
      </div>
      <a-space>
        <a-button @click="triggerCollect">
          <template #icon><SyncOutlined /></template>
          触发采集
        </a-button>
        <a-button @click="reDetect">
          <template #icon><SearchOutlined /></template>
          重新检测
        </a-button>
        <a-button v-if="detail.status === 'active'" @click="doPause">
          <template #icon><PauseCircleOutlined /></template>
          暂停
        </a-button>
        <a-button v-if="detail.status === 'paused'" type="primary" @click="doResume">
          <template #icon><PlayCircleOutlined /></template>
          恢复
        </a-button>
        <a-button danger @click="doRetire">退役</a-button>
      </a-space>
    </div>

    <a-row :gutter="16">
      <!-- Left column -->
      <a-col :span="16">
        <!-- 基本信息 -->
        <a-card title="基本信息" style="margin-bottom:16px;">
          <a-descriptions :column="2" size="small" bordered>
            <a-descriptions-item label="网站名称">{{ detail.name }}</a-descriptions-item>
            <a-descriptions-item label="栏目名称">{{ detail.columnName }}</a-descriptions-item>
            <a-descriptions-item label="模板类型">
              <a-tag :color="templateColor(detail.templateType)">{{ detail.templateType }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="所属平台">{{ detail.platform || '—' }}</a-descriptions-item>
            <a-descriptions-item label="地区">{{ detail.region || '—' }}</a-descriptions-item>
            <a-descriptions-item label="优先级">{{ detail.priority }}</a-descriptions-item>
            <a-descriptions-item label="采集间隔">
              {{ detail.checkInterval ? `${detail.checkInterval}秒` : '—' }}
            </a-descriptions-item>
            <a-descriptions-item label="编码">{{ detail.encoding || 'UTF-8' }}</a-descriptions-item>
            <a-descriptions-item label="创建时间" :span="2">{{ detail.createdAt || '—' }}</a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- 最近采集日志 -->
        <a-card title="最近采集日志" style="margin-bottom:16px;">
          <a-table
            :columns="logColumns"
            :data-source="recentLogs"
            :pagination="false"
            size="small"
            row-key="id"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="logStatusColor(record.status)">{{ record.status }}</a-tag>
              </template>
            </template>
          </a-table>
        </a-card>

        <!-- 采集规则 -->
        <a-card title="采集规则">
          <template #extra>
            <a-button type="link" size="small" @click="goEditRule">编辑规则</a-button>
          </template>
          <div v-if="detail.listRule || detail.detailRule">
            <div v-if="detail.listRule" style="margin-bottom:12px;">
              <div style="font-size:12px;color:#8c8c8c;margin-bottom:4px;">列表规则</div>
              <pre class="rule-code">{{ formatJson(detail.listRule) }}</pre>
            </div>
            <div v-if="detail.detailRule">
              <div style="font-size:12px;color:#8c8c8c;margin-bottom:4px;">详情规则</div>
              <pre class="rule-code">{{ formatJson(detail.detailRule) }}</pre>
            </div>
          </div>
          <a-empty v-else description="暂无规则数据" />
        </a-card>
      </a-col>

      <!-- Right column -->
      <a-col :span="8">
        <!-- 运行状态 -->
        <a-card title="运行状态" style="margin-bottom:16px;">
          <div style="text-align:center;margin-bottom:16px;">
            <div
              style="font-size:48px;font-weight:700;font-family:'JetBrains Mono',monospace;"
              :style="{ color: healthDotColor(detail.healthScore) }"
            >
              {{ detail.healthScore ?? '—' }}
            </div>
            <div style="font-size:12px;color:#8c8c8c;">健康评分</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">状态</span>
              <a-tag :color="statusColor(detail.status)">{{ statusLabel(detail.status) }}</a-tag>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">最后采集</span>
              <span>{{ detail.lastSuccessAt || '—' }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">静默天数</span>
              <span>{{ detail.quietDays != null ? `${detail.quietDays}天` : '—' }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">累计文章</span>
              <span>{{ detail.totalArticles ?? '—' }}篇</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">连续失败</span>
              <span>{{ detail.failCount ?? 0 }}次</span>
            </div>
          </div>
        </a-card>

        <!-- 最近采集日志 -->
        <a-card style="margin-bottom:0;">
          <template #title>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span>最近采集日志</span>
              <span style="font-size:12px;color:#8c8c8c;">共 {{ recentLogs.length }} 条</span>
            </div>
          </template>
          <a-timeline v-if="recentLogs.length">
            <a-timeline-item
              v-for="log in displayedLogs"
              :key="log.id"
              :color="logStatusColor(log.action || log.level)"
            >
              <div style="font-size:11px;color:#8c8c8c;">{{ log.created_at }}</div>
              <div style="font-size:12px;margin-top:2px;">
                <a-tag :color="logActionColor(log.action)" size="small" style="margin-right:4px;">
                  {{ logActionLabel(log.action) }}
                </a-tag>
                <a-tag v-if="log.level === 'ERROR'" color="red" size="small" style="margin-right:4px;">ERROR</a-tag>
                {{ log.message || '' }}
              </div>
              <div v-if="log.operator" style="font-size:11px;color:#bfbfbf;margin-top:2px;">
                操作人：{{ log.operator }}
              </div>
            </a-timeline-item>
          </a-timeline>
          <div v-if="recentLogs.length > 5" style="text-align:center;margin-top:8px;">
            <a-button type="link" size="small" @click="logsExpanded = !logsExpanded">
              {{ logsExpanded ? '收起' : `展开全部 ${recentLogs.length} 条` }}
            </a-button>
          </div>
          <a-empty v-if="!recentLogs.length" description="暂无日志记录" />
        </a-card>
      </a-col>
    </a-row>
  </div>

  <!-- Loading state -->
  <div v-else-if="loading" style="text-align:center;padding:80px;">
    <a-spin size="large" />
  </div>

  <!-- Error state -->
  <a-result v-else status="404" title="采集源不存在" sub-title="该采集源可能已被删除或不存在">
    <template #extra>
      <router-link to="/sources">
        <a-button type="primary">返回列表</a-button>
      </router-link>
    </template>
  </a-result>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  SyncOutlined,
  SearchOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons-vue'
import { sourceApi } from '../../api/source.js'
import request from '../../api/request.js'

const route = useRoute()
const router = useRouter()

const detail = ref(null)
const recentLogs = ref([])
const loading = ref(false)
const logsExpanded = ref(false)

const displayedLogs = computed(() => {
  return logsExpanded.value ? recentLogs.value : recentLogs.value.slice(0, 5)
})

const logColumns = [
  { title: '时间', dataIndex: 'createdAt', key: 'createdAt', width: 130 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '耗时', dataIndex: 'duration', key: 'duration', width: 70 },
  { title: '发现篇数', dataIndex: 'foundCount', key: 'foundCount', width: 80 },
  { title: '新增篇数', dataIndex: 'newCount', key: 'newCount', width: 80 },
  { title: '说明', dataIndex: 'message', key: 'message' },
]

function templateColor(type) {
  const map = { A: 'purple', B: 'orange', C: 'blue', D: 'purple', G: 'red', H: 'green', I: 'cyan', J: 'default' }
  return map[type] || 'default'
}

function statusColor(status) {
  const map = { active: 'success', error: 'error', pending_review: 'warning', paused: 'default', retired: 'default' }
  return map[status] || 'default'
}

function statusLabel(status) {
  const map = { active: '活跃', error: '异常', pending_review: '待审核', paused: '暂停', retired: '退役', pending_detect: '待检测' }
  return map[status] || status
}

function healthDotColor(score) {
  if (score >= 90) return '#52c41a'
  if (score >= 70) return '#1677ff'
  if (score >= 50) return '#fa8c16'
  return '#ff4d4f'
}

function logStatusColor(status) {
  if (status === 'success' || status === '成功' || status === 'crawl_success') return 'green'
  if (status === 'error' || status === '失败' || status === 'crawl_failed' || status === 'ERROR') return 'red'
  if (status === 'WARN' || status === 'detect' || status === 'trial') return 'orange'
  return 'blue'
}

function logActionColor(action) {
  const map = {
    crawl_success: 'green', crawl_failed: 'red',
    detect: 'blue', trial: 'cyan',
    approve: 'green', reject: 'red',
    pause: 'default', resume: 'green', retire: 'default', reset: 'orange',
  }
  return map[action] || 'default'
}

function logActionLabel(action) {
  const map = {
    crawl_success: '采集成功', crawl_failed: '采集失败',
    detect: '检测', trial: '试采',
    approve: '审批通过', reject: '审批拒绝',
    pause: '暂停', resume: '恢复', retire: '退役', reset: '重置',
  }
  return map[action] || action || '—'
}

/** 将 JSON 字符串或对象格式化为带缩进的字符串 */
function formatJson(val) {
  try {
    if (typeof val === 'string') return JSON.stringify(JSON.parse(val), null, 2)
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

const ruleId = ref(null)  // 该采集源对应的规则 ID（用于跳转编辑页）

/** 加载采集源详情 + 关联规则 ID */
async function fetchDetail() {
  loading.value = true
  try {
    const res = await sourceApi.detail(route.params.id)
    detail.value = res || {}
    recentLogs.value = res?.recentLogs || res?.recent_logs || []

    // 查询该采集源的规则ID
    try {
      const rulesRes = await request.get('/api/rules', { params: { sourceId: route.params.id, page: 1, pageSize: 1 } })
      const rules = rulesRes?.records || []
      if (rules.length > 0) ruleId.value = rules[0].id
    } catch { /* ignore */ }
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

/** 跳转规则编辑页；无规则时提示用户先执行检测 */
function goEditRule() {
  if (ruleId.value) {
    router.push(`/rules/${ruleId.value}/edit`)
  } else {
    message.warning('该采集源暂无规则，请先执行检测')
  }
}

async function triggerCollect() {
  try {
    await sourceApi.detect(route.params.id)
    message.success('已触发采集')
  } catch {
    // handled globally
  }
}

async function reDetect() {
  try {
    await sourceApi.detect(route.params.id)
    message.success('已触发重新检测')
  } catch {
    // handled globally
  }
}

async function doPause() {
  Modal.confirm({
    title: '暂停采集源',
    content: '确认暂停该采集源？',
    onOk: async () => {
      try {
        await sourceApi.pause(route.params.id)
        message.success('已暂停')
        fetchDetail()
      } catch {
        // handled globally
      }
    },
  })
}

async function doResume() {
  try {
    await sourceApi.resume(route.params.id)
    message.success('已恢复')
    fetchDetail()
  } catch {
    // handled globally
  }
}

async function doRetire() {
  Modal.confirm({
    title: '退役采集源',
    content: '确认退役该采集源？此操作不可撤销。',
    okType: 'danger',
    onOk: async () => {
      try {
        await sourceApi.delete(route.params.id)
        message.success('已退役')
        router.push('/sources')
      } catch {
        // handled globally
      }
    },
  })
}

onMounted(fetchDetail)
</script>

<style scoped>
.rule-code {
  background: #f6f8fa;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
}
</style>
