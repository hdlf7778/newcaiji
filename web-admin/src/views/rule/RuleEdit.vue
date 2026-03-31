<!--
  规则编辑页（RuleEdit）

  功能：
    - 左侧双编辑器：列表规则 + 详情规则（JSON 文本编辑）
    - 每个编辑器支持三个操作：测试、LLM 自动生成、重置为初始值
    - 右侧实时展示测试结果（列表匹配条目 / 详情页解析预览）
    - 详情测试依赖列表测试结果中的第一条文章 URL
-->
<template>
  <div>
    <!-- Header -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <a-button @click="$router.back()">← 返回</a-button>
      <h2 style="font-size:18px;font-weight:600;margin:0;">规则编辑</h2>
    </div>

    <!-- Source info bar -->
    <a-card :body-style="{ padding: '12px 16px' }" style="margin-bottom:16px;">
      <a-row :gutter="24">
        <a-col :span="8">
          <span style="color:#8c8c8c;font-size:13px;">采集源：</span>
          <router-link v-if="sourceInfo.id" :to="`/sources/${sourceInfo.id}`" style="font-weight:600;color:#1677ff;">
            {{ sourceInfo.name || '—' }}
          </router-link>
          <span v-else style="font-weight:600;">加载中...</span>
        </a-col>
        <a-col :span="12">
          <span style="color:#8c8c8c;font-size:13px;">网址：</span>
          <a :href="safeUrl(sourceInfo.url)" target="_blank" rel="noopener noreferrer" style="color:#1677ff;word-break:break-all;font-size:13px;">
            {{ sourceInfo.url || '—' }}
          </a>
        </a-col>
        <a-col :span="4" style="text-align:right;">
          <a-tag v-if="sourceInfo.template" :color="templateColor(sourceInfo.template)">
            {{ templateLabel(sourceInfo.template) }}
          </a-tag>
        </a-col>
      </a-row>
    </a-card>

    <a-row :gutter="16">
      <!-- Left: Editors -->
      <a-col :span="12">
        <!-- 列表规则 -->
        <a-card style="margin-bottom:16px;">
          <template #title>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span>列表规则 (list_rule)</span>
              <a-space>
                <a-button size="small" type="primary" :loading="listTestLoading" @click="onTestList">测试列表</a-button>
                <a-button size="small" :loading="listLlmLoading" @click="onLlmList">LLM生成</a-button>
                <a-popconfirm title="确认恢复为初始列表规则？" @confirm="onResetList">
                  <a-button size="small">重置</a-button>
                </a-popconfirm>
              </a-space>
            </div>
          </template>
          <a-textarea
            v-model:value="listRuleText"
            :rows="10"
            style="font-family:'JetBrains Mono',monospace;font-size:12px;background:#1e1e1e;color:#d4d4d4;border-color:#3a3a3a;resize:vertical;"
          />
        </a-card>

        <!-- 详情规则 -->
        <a-card style="margin-bottom:16px;">
          <template #title>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span>详情规则 (detail_rule)</span>
              <a-space>
                <a-button size="small" type="primary" :loading="detailTestLoading" @click="onTestDetail">测试详情</a-button>
                <a-button size="small" :loading="detailLlmLoading" @click="onLlmDetail">LLM生成</a-button>
                <a-popconfirm title="确认恢复为初始详情规则？" @confirm="onResetDetail">
                  <a-button size="small">重置</a-button>
                </a-popconfirm>
              </a-space>
            </div>
          </template>
          <a-textarea
            v-model:value="detailRuleText"
            :rows="10"
            style="font-family:'JetBrains Mono',monospace;font-size:12px;background:#1e1e1e;color:#d4d4d4;border-color:#3a3a3a;resize:vertical;"
          />
        </a-card>

        <!-- Save -->
        <a-space>
          <a-button type="primary" size="large" :loading="saveLoading" @click="onSave">
            保存全部规则
          </a-button>
        </a-space>
      </a-col>

      <!-- Right: Test Results -->
      <a-col :span="12">
        <!-- 列表规则测试结果 -->
        <a-card style="margin-bottom:16px;">
          <template #title>列表规则测试结果</template>
          <a-spin :spinning="listTestLoading">
            <div v-if="!listTestResult && !listTestLoading" style="color:#8c8c8c;text-align:center;padding:30px 0;">
              点击「测试列表」查看采集结果
            </div>
            <template v-if="listTestResult">
              <a-alert
                :type="listTestResult.success ? 'success' : 'error'"
                :message="listTestResult.success ? `匹配到 ${listTestResult.count} 篇文章` : `解析失败：${listTestResult.error}`"
                show-icon
                style="margin-bottom:12px;"
              />
              <div v-if="listTestResult.articles?.length">
                <div
                  v-for="(a, i) in listTestResult.articles"
                  :key="i"
                  style="border:1px solid #f0f0f0;border-radius:6px;padding:8px 12px;margin-bottom:6px;background:#fafafa;"
                >
                  <div style="font-weight:600;font-size:13px;">{{ a.title }}</div>
                  <div style="font-size:12px;color:#8c8c8c;display:flex;gap:12px;margin-top:2px;">
                    <span v-if="a.publish_date || a.date">{{ a.publish_date || a.date }}</span>
                    <a :href="safeUrl(a.url)" target="_blank" rel="noopener noreferrer" style="color:#1677ff;word-break:break-all;">{{ (a.url || '').slice(0, 60) }}{{ (a.url || '').length > 60 ? '...' : '' }}</a>
                  </div>
                </div>
              </div>
            </template>
          </a-spin>
        </a-card>

        <!-- 详情规则测试结果 -->
        <a-card>
          <template #title>详情规则测试结果</template>
          <a-spin :spinning="detailTestLoading">
            <div v-if="!detailTestResult && !detailTestLoading" style="color:#8c8c8c;text-align:center;padding:30px 0;">
              点击「测试详情」查看采集结果（需先测试列表）
            </div>
            <template v-if="detailTestResult">
              <a-alert
                :type="detailTestResult.success ? 'success' : 'error'"
                :message="detailTestResult.success ? `详情页解析成功` : `解析失败：${detailTestResult.error}`"
                show-icon
                style="margin-bottom:12px;"
              />
              <div v-if="detailTestResult.success" style="border:1px solid #f0f0f0;border-radius:6px;padding:12px;background:#fafafa;">
                <div style="font-weight:700;font-size:15px;margin-bottom:8px;">{{ detailTestResult.title }}</div>
                <div style="font-size:12px;color:#8c8c8c;margin-bottom:8px;display:flex;gap:16px;">
                  <span v-if="detailTestResult.publish_date">发布：{{ detailTestResult.publish_date }}</span>
                  <span v-if="detailTestResult.author">作者：{{ detailTestResult.author }}</span>
                  <span>正文长度：{{ detailTestResult.content_length }} 字</span>
                </div>
                <div style="font-size:13px;color:#595959;line-height:1.8;max-height:250px;overflow:auto;white-space:pre-wrap;">{{ detailTestResult.content_preview }}</div>
              </div>
            </template>
          </a-spin>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import request from '../../api/request.js'
import { safeUrl } from '../../utils/safeUrl.js'

const route = useRoute()
const ruleId = route.params.id

const sourceInfo = ref({})          // 关联的采集源信息
const listRuleText = ref('')        // 列表规则 JSON 文本（可编辑）
const detailRuleText = ref('')      // 详情规则 JSON 文本（可编辑）
const originalListRule = ref('')    // 初始列表规则（用于"重置"功能）
const originalDetailRule = ref('')  // 初始详情规则（用于"重置"功能）

const listTestResult = ref(null)
const detailTestResult = ref(null)
const listTestLoading = ref(false)
const detailTestLoading = ref(false)
const listLlmLoading = ref(false)
const detailLlmLoading = ref(false)
const saveLoading = ref(false)

const TEMPLATE_MAP = {
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
function templateLabel(t) { const m = TEMPLATE_MAP[t]; return m ? `${m.letter} ${m.label}` : t }
function templateColor(t) { return TEMPLATE_MAP[t]?.color || 'default' }

/** 安全解析 JSON，失败返回 null */
function safeParse(text) {
  try { return JSON.parse(text) } catch { return null }
}
function safeStringify(obj) {
  try { return JSON.stringify(obj, null, 2) } catch { return '' }
}

async function fetchRule() {
  try {
    const rule = await request.get(`/api/rules/${ruleId}`)
    listRuleText.value = safeStringify(safeParse(rule.list_rule) || {})
    detailRuleText.value = safeStringify(safeParse(rule.detail_rule) || {})
    originalListRule.value = listRuleText.value
    originalDetailRule.value = detailRuleText.value

    // Fetch source info
    if (rule.source_id) {
      try {
        const src = await request.get(`/api/sources/${rule.source_id}`)
        sourceInfo.value = { id: src.id, name: src.name, url: src.url, template: src.template || 'STATIC_LIST' }
      } catch { sourceInfo.value = { id: rule.source_id, name: `#${rule.source_id}`, url: '' } }
    }
  } catch {
    message.error('加载规则失败')
  }
}

async function onTestList() {
  const listRule = safeParse(listRuleText.value)
  if (!listRule) { message.error('列表规则 JSON 格式错误'); return }

  listTestLoading.value = true
  listTestResult.value = null
  try {
    const res = await request.post('/api/rules/test-list', {
      source_id: sourceInfo.value.id,
      url: sourceInfo.value.url,
      template: sourceInfo.value.template,
      list_rule: listRule,
    })
    listTestResult.value = res || { success: false, error: '无返回数据' }
  } catch (e) {
    listTestResult.value = { success: false, error: e.message || '请求失败', count: 0, articles: [] }
  } finally {
    listTestLoading.value = false
  }
}

/** 测试详情规则：使用列表测试结果的第一条文章 URL 作为输入 */
async function onTestDetail() {
  const detailRule = safeParse(detailRuleText.value)
  if (!detailRule) { message.error('详情规则 JSON 格式错误'); return }

  // Need an article URL from list test result
  const articleUrl = listTestResult.value?.articles?.[0]?.url
  if (!articleUrl) { message.warning('请先测试列表规则，获取文章URL后再测试详情'); return }

  detailTestLoading.value = true
  detailTestResult.value = null
  try {
    const res = await request.post('/api/rules/test-detail', {
      source_id: sourceInfo.value.id,
      url: articleUrl,
      template: sourceInfo.value.template,
      detail_rule: detailRule,
    })
    detailTestResult.value = res || { success: false, error: '无返回数据' }
  } catch (e) {
    detailTestResult.value = { success: false, error: e.message || '请求失败' }
  } finally {
    detailTestLoading.value = false
  }
}

function onResetList() {
  listRuleText.value = originalListRule.value
  message.success('列表规则已恢复为初始内容')
}

function onResetDetail() {
  detailRuleText.value = originalDetailRule.value
  message.success('详情规则已恢复为初始内容')
}

async function onLlmList() {
  listLlmLoading.value = true
  try {
    const res = await request.post('/api/rules/llm-generate', {
      source_id: sourceInfo.value.id,
      url: sourceInfo.value.url,
      type: 'list',
    })
    if (res?.list_rule) {
      listRuleText.value = safeStringify(typeof res.list_rule === 'string' ? safeParse(res.list_rule) : res.list_rule)
      message.success('列表规则 LLM 生成完成')
    } else {
      message.warning('LLM 未返回列表规则')
    }
  } catch (e) {
    message.error('LLM 生成失败: ' + (e.message || ''))
  } finally {
    listLlmLoading.value = false
  }
}

async function onLlmDetail() {
  detailLlmLoading.value = true
  try {
    const res = await request.post('/api/rules/llm-generate', {
      source_id: sourceInfo.value.id,
      url: sourceInfo.value.url,
      type: 'detail',
    })
    if (res?.detail_rule) {
      detailRuleText.value = safeStringify(typeof res.detail_rule === 'string' ? safeParse(res.detail_rule) : res.detail_rule)
      message.success('详情规则 LLM 生成完成')
    } else {
      message.warning('LLM 未返回详情规则')
    }
  } catch (e) {
    message.error('LLM 生成失败: ' + (e.message || ''))
  } finally {
    detailLlmLoading.value = false
  }
}

async function onSave() {
  const listRule = safeParse(listRuleText.value)
  const detailRule = safeParse(detailRuleText.value)
  if (!listRule) { message.error('列表规则 JSON 格式错误'); return }
  if (!detailRule) { message.error('详情规则 JSON 格式错误'); return }

  saveLoading.value = true
  try {
    await request.put(`/api/rules/${ruleId}`, {
      list_rule: JSON.stringify(listRule),
      detail_rule: JSON.stringify(detailRule),
    })
    message.success('规则已保存')
  } catch {
    // handled by interceptor
  } finally {
    saveLoading.value = false
  }
}

onMounted(fetchRule)
</script>
