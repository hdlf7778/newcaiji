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
        <a-button
          v-if="!isActive"
          type="primary"
          @click="doApprove"
        >
          <template #icon><CheckCircleOutlined /></template>
          上线
        </a-button>
        <a-button v-if="isActive" @click="doPause">
          <template #icon><PauseCircleOutlined /></template>
          暂停
        </a-button>
        <a-button v-if="isPaused" type="primary" @click="doResume">
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
            <a-descriptions-item label="栏目名称">{{ detail.column_name || detail.columnName || '—' }}</a-descriptions-item>
            <a-descriptions-item label="模板类型">
              <a-tag :color="templateTagColor(detail.template)">{{ templateTagLabel(detail.template) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="试采评分">
              <a-tag v-if="detail.trial_score != null" :color="scoreColor(detail.trial_score)">
                {{ detail.trial_score }}
              </a-tag>
              <span v-else style="color:#bfbfbf;">未试采</span>
            </a-descriptions-item>
            <a-descriptions-item label="地区">{{ detail.region || '—' }}</a-descriptions-item>
            <a-descriptions-item label="优先级">{{ detail.priority }}</a-descriptions-item>
            <a-descriptions-item label="编码">{{ detail.encoding || 'UTF-8' }}</a-descriptions-item>
            <a-descriptions-item label="创建时间">{{ detail.created_at || detail.createdAt || '—' }}</a-descriptions-item>
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
          <div v-if="ruleData">
            <div style="margin-bottom:12px;">
              <div style="font-size:12px;color:#8c8c8c;margin-bottom:4px;">
                列表规则 (list_rule)
                <a-tag size="small" style="margin-left:8px;">版本 {{ ruleData.rule_version || 1 }}</a-tag>
                <a-tag size="small" :color="ruleData.generated_by === 'llm' ? 'blue' : 'green'">{{ ruleData.generated_by || '—' }}</a-tag>
              </div>
              <pre class="rule-code">{{ formatJson(ruleData.list_rule) }}</pre>
            </div>
            <div>
              <div style="font-size:12px;color:#8c8c8c;margin-bottom:4px;">详情规则 (detail_rule)</div>
              <pre class="rule-code">{{ formatJson(ruleData.detail_rule) }}</pre>
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
              :style="{ color: healthDotColor(detail.health_score || detail.healthScore) }"
            >
              {{ detail.health_score ?? detail.healthScore ?? '—' }}
            </div>
            <div style="font-size:12px;color:#8c8c8c;">健康评分</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">状态</span>
              <a-tag :color="statusColor(detail.status)">{{ statusLabel(detail.status) }}</a-tag>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">试采评分</span>
              <span v-if="detail.trial_score != null">
                <a-tag :color="scoreColor(detail.trial_score)">{{ detail.trial_score }}</a-tag>
              </span>
              <span v-else style="color:#bfbfbf;">—</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">最后采集</span>
              <span>{{ detail.last_success_at || detail.lastSuccessAt || '—' }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">静默天数</span>
              <span>{{ (detail.quiet_days ?? detail.quietDays) != null ? `${detail.quiet_days ?? detail.quietDays}天` : '—' }}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">累计文章</span>
              <span>{{ detail.total_articles ?? detail.totalArticles ?? '—' }}篇</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span style="color:#8c8c8c;">连续失败</span>
              <span>{{ detail.fail_count ?? detail.failCount ?? 0 }}次</span>
            </div>
          </div>
        </a-card>

        <!-- 试采结果 -->
        <a-card style="margin-bottom:0;">
          <template #title>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span>试采结果</span>
              <a-tag v-if="detail.trial_score != null" :color="scoreColor(detail.trial_score)">
                评分 {{ detail.trial_score }}
              </a-tag>
            </div>
          </template>

          <!-- 试采文章列表 -->
          <div v-if="trialArticles.length">
            <div
              v-for="(article, idx) in trialArticles"
              :key="idx"
              style="border:1px solid #f0f0f0;border-radius:6px;padding:8px 12px;margin-bottom:6px;cursor:pointer;transition:all 0.2s;"
              @click="openArticleModal(article)"
              @mouseenter="$event.currentTarget.style.borderColor='#1677ff'"
              @mouseleave="$event.currentTarget.style.borderColor='#f0f0f0'"
            >
              <div style="font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                📄 {{ article.title || '无标题' }}
              </div>
              <div style="font-size:11px;color:#bfbfbf;margin-top:2px;">
                {{ article.publish_date || '' }} · {{ article.content_length || 0 }}字
              </div>
            </div>
          </div>

          <!-- 加载中 -->
          <div v-else-if="trialLoading" style="text-align:center;padding:20px;">
            <a-spin tip="正在试采..." />
          </div>
          <!-- 无试采数据 -->
          <div v-else>
            <a-alert
              v-if="trialError"
              type="error"
              :message="trialError"
              show-icon
              style="margin-bottom:8px;"
            />
            <a-empty v-else description="暂无试采数据，点击下方按钮开始试采" />
          </div>

          <!-- 重新试采按钮 -->
          <div style="margin-top:10px;text-align:center;">
            <a-button size="small" :loading="trialLoading" @click="runTrial">
              🧪 重新试采
            </a-button>
          </div>
        </a-card>

        <!-- 智能诊断与修复 -->
        <a-card
          v-if="showDiagnosis"
          title="智能诊断"
          size="small"
          style="margin-top:16px;"
        >
          <!-- Not yet diagnosed -->
          <div v-if="!diagnosisResult && !diagnosing && !repairing">
            <a-alert
              message="试采未能获取到文章内容"
              description="点击下方按钮，系统将自动分析原因并尝试修复"
              type="warning"
              show-icon
              style="margin-bottom:12px;"
            />
            <a-space>
              <a-button @click="runDiagnose" :loading="diagnosing">
                <template #icon><SearchOutlined /></template>
                诊断分析
              </a-button>
              <a-button type="primary" @click="runAutoRepair" :loading="repairing">
                <template #icon><ToolOutlined /></template>
                一键修复
              </a-button>
            </a-space>
          </div>

          <!-- Diagnosing -->
          <div v-else-if="diagnosing" style="text-align:center;padding:20px;">
            <a-spin tip="正在诊断中..." />
          </div>

          <!-- Repairing -->
          <div v-else-if="repairing" style="text-align:center;padding:20px;">
            <a-spin tip="正在自动修复中，可能需要30秒..." />
          </div>

          <!-- Diagnosis result (before repair) -->
          <div v-else-if="diagnosisResult && !repairResult">
            <div style="margin-bottom:12px;">
              <a-tag :color="diagnosisResult.reachable ? 'green' : 'red'">
                {{ diagnosisResult.reachable ? '站点可达' : '站点不可达' }}
              </a-tag>
              <a-tag v-if="diagnosisResult.redirected" color="orange">有重定向</a-tag>
              <a-tag v-if="diagnosisResult.is_js_rendered" color="purple">JS动态渲染</a-tag>
              <a-tag v-if="diagnosisResult.is_forbidden" color="red">403拒绝</a-tag>
            </div>

            <a-alert
              v-for="(finding, idx) in diagnosisResult.diagnosis"
              :key="idx"
              :message="finding"
              :type="finding.includes('不可达') || finding.includes('403') || finding.includes('失败') ? 'error' : finding.includes('重定向') || finding.includes('动态渲染') ? 'warning' : 'info'"
              show-icon
              style="margin-bottom:6px;"
              :banner="true"
            />

            <div v-if="diagnosisResult.suggested_actions?.length" style="margin-top:12px;">
              <div style="font-size:12px;color:#8c8c8c;margin-bottom:6px;">建议修复步骤：</div>
              <a-steps :current="-1" direction="vertical" size="small" style="padding-left:4px;">
                <a-step v-for="action in diagnosisResult.suggested_actions" :key="action" :title="actionLabel(action)" />
              </a-steps>
            </div>

            <div style="margin-top:12px;">
              <a-button type="primary" @click="runAutoRepair" :loading="repairing">
                <template #icon><ToolOutlined /></template>
                执行修复
              </a-button>
            </div>
          </div>

          <!-- Repair result -->
          <div v-if="repairResult">
            <a-result
              :status="repairResult.success ? 'success' : 'warning'"
              :title="repairResult.success ? '修复成功' : '修复完成，可能需要人工调整'"
              :sub-title="'评分: ' + (repairResult.previousScore ?? 0) + ' → ' + (repairResult.newScore ?? 0)"
              style="padding:12px 0;"
            />

            <div v-if="repairResult.repairLog?.length" style="margin-top:8px;">
              <a-timeline style="padding-left:4px;">
                <a-timeline-item
                  v-for="(log, idx) in repairResult.repairLog"
                  :key="idx"
                  :color="log.success ? 'green' : 'red'"
                >
                  <span style="font-weight:500;">{{ log.name }}</span>
                  <span style="margin-left:8px;color:#8c8c8c;font-size:12px;">{{ log.message }}</span>
                </a-timeline-item>
              </a-timeline>
            </div>

            <!-- Post-repair guidance -->
            <div v-if="!repairResult.success" style="margin-top:12px;">
              <a-alert type="info" show-icon style="margin-bottom:8px;">
                <template #message>
                  <span v-if="needsBrowser">该网站为JS动态渲染页面，需要启动浏览器采集服务</span>
                  <span v-else>自动修复未能解决问题，建议手动调整</span>
                </template>
                <template #description>
                  <div style="font-size:12px;line-height:2;">
                    <div v-if="needsBrowser">
                      <div><strong>该网站为JS动态渲染页面，自动修复已尝试所有HTTP策略均未成功。</strong></div>
                      <a-divider style="margin:8px 0;" />
                      <div><strong>方案一：启动浏览器采集服务</strong></div>
                      <div style="color:#8c8c8c;">在服务器终端执行：<code style="background:#f5f5f5;padding:2px 6px;border-radius:3px;">python3 worker.py --queue browser</code></div>
                      <div style="color:#8c8c8c;">启动后点击下方「重新试采」按钮验证</div>
                      <a-divider style="margin:8px 0;" />
                      <div><strong>方案二：手动查找API接口</strong></div>
                      <div style="color:#8c8c8c;">1. 浏览器打开网站，按 F12 → Network → 筛选 Fetch/XHR</div>
                      <div style="color:#8c8c8c;">2. 刷新页面，找到返回文章列表的 JSON 接口</div>
                      <div style="color:#8c8c8c;">3. 到「规则编辑」页面，将模板改为「C API接口」，填入 API 地址</div>
                      <a-divider style="margin:8px 0;" />
                      <div><strong>方案三：退役该采集源</strong></div>
                      <div style="color:#8c8c8c;">该URL可能不是有效的文章列表页，或网站API存在服务端限制</div>
                    </div>
                    <div v-else>
                      <div>1. 到「规则编辑」页面，点击「LLM生成」重新生成规则</div>
                      <div>2. 手动修改 CSS 选择器适配目标网站结构</div>
                      <div>3. 检查网站是否需要登录或有其他访问限制</div>
                    </div>
                  </div>
                </template>
              </a-alert>
              <a-space wrap>
                <a-button @click="runAutoRepair" :loading="repairing">再次修复</a-button>
                <a-button @click="showManualAssist = !showManualAssist">
                  <template #icon><EditOutlined /></template>
                  人工辅助修复
                </a-button>
                <a-button @click="loadTrialArticles">重新试采</a-button>
                <router-link v-if="ruleData?.id" :to="'/rules/' + ruleData.id + '/edit'">
                  <a-button type="primary">编辑规则</a-button>
                </router-link>
                <a-popconfirm title="确定要退役该采集源吗？退役后将不再采集。" @confirm="retireSource">
                  <a-button danger>退役</a-button>
                </a-popconfirm>
              </a-space>

              <!-- Manual assist input -->
              <div v-if="showManualAssist" style="margin-top:12px;">
                <a-divider style="margin:8px 0;" />
                <div style="font-size:13px;font-weight:500;margin-bottom:8px;">人工辅助修复</div>
                <div style="font-size:12px;color:#8c8c8c;margin-bottom:8px;">
                  请输入您对网页的分析结果，例如：
                  <ul style="margin:4px 0;padding-left:16px;">
                    <li>找到了 JSON API 接口：https://xxx/api/list?page=1</li>
                    <li>文章列表在 .news-list &gt; li 容器中</li>
                    <li>需要带 Cookie 或特定 Referer 头</li>
                    <li>数据通过 iframe 加载，src 是 /frame/list.html</li>
                  </ul>
                </div>
                <a-textarea
                  v-model:value="manualHint"
                  placeholder="输入您的分析结果，系统将据此自动生成采集规则并试采..."
                  :rows="4"
                  :maxlength="2000"
                  show-count
                  style="margin-bottom:8px;"
                />
                <a-button
                  type="primary"
                  :loading="manualAssisting"
                  :disabled="!manualHint?.trim()"
                  @click="runManualAssist"
                >
                  <template #icon><ToolOutlined /></template>
                  提交并自动调试
                </a-button>
              </div>
            </div>
          </div>
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

  <!-- 试采文章详情弹窗 -->
  <a-modal
    v-model:open="articleModalVisible"
    :title="currentArticle?.title || '文章详情'"
    width="800px"
    :footer="null"
  >
    <div v-if="currentArticle" style="padding:8px 0;">
      <!-- 元信息 -->
      <div style="margin-bottom:16px;padding:10px 14px;background:#f6f8fa;border-radius:6px;font-size:13px;color:#666;display:flex;gap:16px;flex-wrap:wrap;">
        <span v-if="currentArticle.publish_date">发布时间：<strong>{{ currentArticle.publish_date }}</strong></span>
        <span>试采时间：<strong>{{ detail?.trial_at || '—' }}</strong></span>
        <span v-if="currentArticle.content_length">正文长度：<strong>{{ currentArticle.content_length }} 字</strong></span>
        <a v-if="currentArticle.url" :href="safeUrl(currentArticle.url)" target="_blank" rel="noopener noreferrer" style="color:#1677ff;">查看原文 →</a>
      </div>

      <!-- 正文 -->
      <div style="font-size:14px;color:#333;line-height:2;white-space:pre-wrap;">
        {{ currentArticle.content_preview || '正文为空' }}
      </div>
    </div>
  </a-modal>
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
  CheckCircleOutlined,
  ToolOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'
import { sourceApi } from '../../api/source.js'
import request from '../../api/request.js'
import { templateLabel as templateTagLabel, templateColor as templateTagColor, statusLabel, statusColor, scoreColor } from '../../constants/source.js'
import { safeUrl } from '../../utils/safeUrl.js'
import { useUserStore } from '../../stores/user.js'

const userStore = useUserStore()

const route = useRoute()
const router = useRouter()

const detail = ref(null)
const recentLogs = ref([])
const loading = ref(false)

// 状态判断（兼容大小写）
const isActive = computed(() => {
  const s = (detail.value?.status || '').toLowerCase()
  return s === 'active'
})
const isPaused = computed(() => {
  const s = (detail.value?.status || '').toLowerCase()
  return s === 'paused'
})

// 试采结果
const trialArticles = ref([])
const trialLoading = ref(false)
const trialError = ref('')
const articleModalVisible = ref(false)
const currentArticle = ref(null)

// --- Diagnosis & Repair ---
const diagnosisResult = ref(null)
const diagnosing = ref(false)
const repairing = ref(false)
const repairResult = ref(null)
const showManualAssist = ref(false)
const manualHint = ref('')
const manualAssisting = ref(false)

const showDiagnosis = computed(() => {
  if (!detail.value) return false
  const s = (detail.value.status || '').toUpperCase()
  return s === 'TRIAL_FAILED' || s === 'DETECT_FAILED'
    || detail.value.trial_score === 0
    || (trialError.value && !trialArticles.value.length)
})

const needsBrowser = computed(() => {
  if (!repairResult.value) return false
  const logs = repairResult.value.repairLog || []
  const lastLog = logs[logs.length - 1]
  return lastLog?.message?.includes('\u6D4F\u89C8\u5668') || false
})

const ACTION_LABELS = {
  update_url: '更新URL（跟随重定向）',
  switch_template: '切换采集模板',
  switch_browser_template: '切换为浏览器渲染模板',
  upgrade_anti_bot: '升级反爬策略',
  regenerate_rules: '重新生成采集规则',
  re_trial: '重新试采验证',
  check_later: '稍后重试（目标站点不可达）',
  check_worker: '检查Worker服务状态',
}

function actionLabel(action) {
  return ACTION_LABELS[action] || action
}

async function runManualAssist() {
  if (!manualHint.value?.trim()) {
    message.warning('请输入分析描述')
    return
  }
  manualAssisting.value = true
  repairResult.value = null
  try {
    repairResult.value = await sourceApi.manualAssistRepair(route.params.id, manualHint.value.trim())
    await fetchDetail()
    if (repairResult.value?.success) {
      message.success('人工辅助修复成功！')
      showManualAssist.value = false
    } else {
      message.warning('修复完成但评分仍较低，可调整描述后重试')
    }
  } catch (e) {
    message.error('人工辅助修复失败: ' + (e.message || ''))
  } finally {
    manualAssisting.value = false
  }
}

async function retireSource() {
  try {
    await sourceApi.retire(route.params.id)
    message.success('已退役')
    await fetchDetail()
  } catch (e) {
    message.error('退役失败: ' + (e.message || ''))
  }
}

async function runDiagnose() {
  diagnosing.value = true
  diagnosisResult.value = null
  repairResult.value = null
  try {
    diagnosisResult.value = await sourceApi.diagnose(route.params.id)
  } catch (e) {
    message.error('诊断失败: ' + (e.message || ''))
  } finally {
    diagnosing.value = false
  }
}

async function runAutoRepair() {
  repairing.value = true
  repairResult.value = null
  try {
    repairResult.value = await sourceApi.autoRepair(route.params.id)
    // Refresh page data
    await fetchDetail()
    if (repairResult.value?.success) {
      message.success('自动修复成功！')
    } else {
      message.warning('修复完成但评分仍较低，可尝试手动编辑规则')
    }
  } catch (e) {
    message.error('修复失败: ' + (e.message || ''))
  } finally {
    repairing.value = false
  }
}

function openArticleModal(article) {
  currentArticle.value = article
  articleModalVisible.value = true
}

const logColumns = [
  { title: '时间', dataIndex: 'createdAt', key: 'createdAt', width: 130 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '耗时', dataIndex: 'duration', key: 'duration', width: 70 },
  { title: '发现篇数', dataIndex: 'foundCount', key: 'foundCount', width: 80 },
  { title: '新增篇数', dataIndex: 'newCount', key: 'newCount', width: 80 },
  { title: '说明', dataIndex: 'message', key: 'message' },
]

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

const ruleId = ref(null)
const ruleData = ref(null)

async function fetchDetail() {
  loading.value = true
  try {
    const res = await sourceApi.detail(route.params.id)
    detail.value = res || {}
    recentLogs.value = res?.recentLogs || res?.recent_logs || []

    // 查询该采集源的规则
    try {
      const rulesRes = await request.get('/api/rules', { params: { sourceId: route.params.id, page: 1, pageSize: 1 } })
      const rules = rulesRes?.records || []
      if (rules.length > 0) {
        ruleId.value = rules[0].id
        ruleData.value = rules[0]
      }
    } catch { /* ignore */ }

    // 加载试采结果（调 test-list 获取文章列表）
    loadTrialArticles()
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

/** 加载试采文章列表 */
async function loadTrialArticles() {
  if (!detail.value?.url) return
  trialLoading.value = true
  trialError.value = ''
  try {
    const template = detail.value.template || 'static_list'
    const listRule = ruleData.value?.list_rule ? JSON.parse(ruleData.value.list_rule) : {}
    const res = await request.post('/api/rules/test-list', {
      source_id: detail.value.id,
      url: detail.value.url,
      template: template,
      list_rule: listRule,
    })
    if (res?.success && res.articles?.length) {
      // 获取前5篇的详情（并发请求）
      const detailRule = ruleData.value?.detail_rule ? JSON.parse(ruleData.value.detail_rule) : {}
      const articles = await Promise.all(
        res.articles.slice(0, 5).map(async (a) => {
          try {
            const dRes = await request.post('/api/rules/test-detail', {
              source_id: detail.value.id,
              url: a.url,
              template: template,
              detail_rule: detailRule,
            })
            return {
              title: dRes?.title || a.title,
              url: a.url,
              publish_date: dRes?.publish_date || a.publish_date,
              content_preview: dRes?.content_preview || '',
              content_length: dRes?.content_length || 0,
            }
          } catch {
            return { title: a.title, url: a.url, publish_date: a.publish_date }
          }
        })
      )
      trialArticles.value = articles
    } else {
      trialArticles.value = []
      trialError.value = res?.error || '列表页未匹配到文章，可能是规则不匹配或网站拒绝访问'
    }
  } catch (e) {
    trialArticles.value = []
    trialError.value = e.message || '试采请求失败，请检查网站是否可访问'
  } finally {
    trialLoading.value = false
  }
}

/** 重新试采 */
async function runTrial() {
  trialLoading.value = true
  trialArticles.value = []
  trialError.value = ''
  try {
    const trialRes = await request.post(`/api/sources/${route.params.id}/trial`)
    // 检查试采结果
    const score = trialRes?.score ?? 0
    const count = trialRes?.count ?? 0
    const success = trialRes?.success

    // 重新加载详情
    const res = await sourceApi.detail(route.params.id)
    detail.value = res || {}

    if (success && count > 0) {
      await loadTrialArticles()
      message.success(`试采完成: ${count}篇 评分${score}`)
    } else {
      message.warning(`试采结果: ${count}篇 评分${score}${trialRes?.error ? ' — ' + trialRes.error : ''}`)
    }
  } catch (e) {
    message.error('试采失败: ' + (e.message || ''))
  } finally {
    trialLoading.value = false
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

async function doApprove() {
  Modal.confirm({
    title: '确认上线',
    content: '审批通过并上线此采集源，将进入生产调度开始自动采集。',
    onOk: async () => {
      try {
        await sourceApi.approve(route.params.id, userStore.username)
        message.success('已上线')
        fetchDetail()
      } catch { /* handled */ }
    },
  })
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
