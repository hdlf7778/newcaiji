<!--
  模板列表页（TemplateList）

  功能：
    - 内置模板卡片：展示 10 种内置采集模板及其采集源数、24h 任务数、成功率
    - 自定义模板管理：新增 / 编辑 / 删除，支持 JSON 规则和反爬配置
    - 自定义模板需选择一个基础模板作为采集逻辑的运行基础
-->
<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">模板列表</h2>
    </div>

    <!-- 内置模板 -->
    <h3 style="font-size:15px;color:#595959;margin-bottom:12px;">内置模板（10个）</h3>
    <a-row :gutter="16">
      <a-col :span="8" v-for="t in builtinTemplates" :key="t.code">
        <a-card hoverable style="margin-bottom:16px;">
          <template #title>
            <div style="display:flex;align-items:center;gap:8px;">
              <a-tag :color="t.color">{{ t.letter }}</a-tag>
              <span style="font-weight:600;">{{ t.label }}</span>
            </div>
          </template>
          <template #extra>
            <a-tag :color="t.queue === 'http' ? 'blue' : 'orange'">{{ t.queue }}</a-tag>
          </template>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#888;">采集源数</span>
            <span style="font-weight:600;">{{ t.sourceCount }}</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#888;">24h任务</span>
            <span style="font-weight:600;">{{ t.taskTotal }}</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#888;">成功率</span>
            <span :style="{ fontWeight: 600, color: t.rate >= 95 ? '#52c41a' : t.rate >= 80 ? '#fa8c16' : '#ff4d4f' }">
              {{ t.rate }}%
            </span>
          </div>
          <div style="margin-top:12px;font-size:12px;color:#999;">{{ t.desc }}</div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 自定义模板 -->
    <h3 style="font-size:15px;color:#595959;margin:24px 0 12px;">自定义模板</h3>
    <a-row :gutter="16">
      <a-col :span="8" v-for="ct in customTemplates" :key="ct.id">
        <a-card hoverable style="margin-bottom:16px;">
          <template #title>
            <div style="display:flex;align-items:center;gap:8px;">
              <a-tag color="purple">自定义</a-tag>
              <span style="font-weight:600;">{{ ct.name }}</span>
            </div>
          </template>
          <template #extra>
            <a-space>
              <a-button type="link" size="small" @click="onEditCustom(ct)">编辑</a-button>
              <a-popconfirm title="确认删除此模板？" @confirm="onDeleteCustom(ct.id)">
                <a-button type="link" size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#888;">模板代码</span>
            <span style="font-family:monospace;font-size:12px;">{{ ct.code }}</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#888;">基础模板</span>
            <a-tag size="small">{{ baseTemplateLabel(ct.base_template) }}</a-tag>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#888;">采集源数</span>
            <span style="font-weight:600;">{{ ct.source_count || 0 }}</span>
          </div>
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#888;">状态</span>
            <a-tag :color="ct.enabled ? 'green' : 'default'">{{ ct.enabled ? '启用' : '停用' }}</a-tag>
          </div>
          <div style="margin-top:12px;font-size:12px;color:#999;">{{ ct.description || '暂无说明' }}</div>
        </a-card>
      </a-col>

      <!-- 添加自定义模板入口 -->
      <a-col :span="8">
        <a-card
          hoverable
          style="margin-bottom:16px;border:2px dashed #d9d9d9;display:flex;align-items:center;justify-content:center;min-height:220px;cursor:pointer;"
          :body-style="{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', width: '100%', height: '100%' }"
          @click="onAddCustom"
        >
          <PlusOutlined style="font-size:32px;color:#bfbfbf;margin-bottom:12px;" />
          <span style="font-size:14px;color:#8c8c8c;">添加自定义模板</span>
        </a-card>
      </a-col>
    </a-row>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingId ? '编辑自定义模板' : '添加自定义模板'"
      width="640px"
      @ok="onSave"
      :confirm-loading="saving"
    >
      <a-form :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top:16px;">
        <a-form-item label="模板名称" required>
          <a-input v-model:value="form.name" placeholder="如：浙江政务云专用" />
        </a-form-item>
        <a-form-item label="模板代码" required>
          <a-input v-model:value="form.code" placeholder="如：zj_gov_cloud（英文+下划线）" :disabled="!!editingId" />
          <div style="font-size:12px;color:#999;margin-top:4px;">唯一标识，创建后不可修改</div>
        </a-form-item>
        <a-form-item label="基础模板" required>
          <a-select v-model:value="form.base_template" placeholder="选择继承的基础模板">
            <a-select-option v-for="bt in BASE_TEMPLATES" :key="bt.code" :value="bt.code">
              {{ bt.letter }} {{ bt.label }}
            </a-select-option>
          </a-select>
          <div style="font-size:12px;color:#999;margin-top:4px;">自定义模板基于哪个内置模板的采集逻辑运行</div>
        </a-form-item>
        <a-form-item label="模板说明">
          <a-textarea v-model:value="form.description" placeholder="描述此模板适用的场景" :rows="2" />
        </a-form-item>
        <a-form-item label="默认列表规则">
          <a-textarea
            v-model:value="form.default_list_rule"
            placeholder='{"list_container": "ul", "list_item": "li", "title_selector": "a", ...}'
            :rows="4"
            style="font-family:monospace;font-size:12px;"
          />
          <div style="font-size:12px;color:#999;margin-top:4px;">JSON 格式，使用此模板创建采集源时自动填入</div>
        </a-form-item>
        <a-form-item label="默认详情规则">
          <a-textarea
            v-model:value="form.default_detail_rule"
            placeholder='{"content_selector": ".article-content", "title_selector": "h1", ...}'
            :rows="4"
            style="font-family:monospace;font-size:12px;"
          />
        </a-form-item>
        <a-form-item label="默认反爬配置">
          <a-textarea
            v-model:value="form.default_anti_bot"
            placeholder='{"type": "cookie_auto", "delay_min": 1, "delay_max": 3}'
            :rows="3"
            style="font-family:monospace;font-size:12px;"
          />
        </a-form-item>
        <a-form-item label="启用状态">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import request from '../../api/request.js'

// 10 种内置模板定义（code 与后端枚举对应）
const BASE_TEMPLATES = [
  { code: 'static_list',        letter: 'A', label: '静态列表页',  queue: 'http',    color: 'purple', desc: '服务端渲染的HTML列表页，用CSS选择器提取' },
  { code: 'iframe_loader',      letter: 'B', label: 'iframe加载', queue: 'browser',  color: 'orange', desc: 'iframe嵌套内容，需解析iframe src后二次请求' },
  { code: 'api_json',           letter: 'C', label: 'API接口型',  queue: 'http',    color: 'blue',   desc: '直接调用JSON API获取数据' },
  { code: 'wechat_article',     letter: 'D', label: '微信公众号',  queue: 'http',    color: 'green',  desc: '微信公众号文章，特殊UA和选择器' },
  { code: 'search_discovery',   letter: 'E', label: '搜索监控',   queue: 'http',    color: 'cyan',   desc: '搜索引擎结果页监控' },
  { code: 'auth_required',      letter: 'F', label: '登录态采集',  queue: 'browser',  color: 'red',    desc: '需要登录Cookie才能访问的站点' },
  { code: 'spa_render',         letter: 'G', label: 'SPA渲染',   queue: 'browser',  color: 'volcano', desc: '单页应用，需Playwright渲染JS后提取' },
  { code: 'rss_feed',           letter: 'H', label: 'RSS订阅',   queue: 'http',    color: 'lime',   desc: 'RSS/Atom feed解析' },
  { code: 'gov_cloud_platform', letter: 'I', label: '政务云平台',  queue: 'http',    color: 'geekblue', desc: '政府统一建站平台(JCMS等)，多策略适配' },
  { code: 'captured_api',       letter: 'J', label: '抓包API',   queue: 'http',    color: 'default', desc: '通过抓包获取的隐藏API' },
]

const builtinTemplates = ref(BASE_TEMPLATES.map(t => ({ ...t, sourceCount: 0, taskTotal: 0, rate: 0 })))
const customTemplates = ref([])

// Modal state
const modalVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const form = ref(makeEmptyForm())

function makeEmptyForm() {
  return { name: '', code: '', base_template: '', description: '', default_list_rule: '', default_detail_rule: '', default_anti_bot: '', enabled: true }
}

function baseTemplateLabel(code) {
  const bt = BASE_TEMPLATES.find(t => t.code === code)
  return bt ? `${bt.letter} ${bt.label}` : code
}

function onAddCustom() {
  editingId.value = null
  form.value = makeEmptyForm()
  modalVisible.value = true
}

function onEditCustom(ct) {
  editingId.value = ct.id
  form.value = {
    name: ct.name,
    code: ct.code,
    base_template: ct.base_template,
    description: ct.description || '',
    default_list_rule: ct.default_list_rule || '',
    default_detail_rule: ct.default_detail_rule || '',
    default_anti_bot: ct.default_anti_bot || '',
    enabled: ct.enabled !== false,
  }
  modalVisible.value = true
}

/** 保存自定义模板（新增或编辑），保存前校验必填项和 JSON 格式 */
async function onSave() {
  if (!form.value.name?.trim()) { message.error('请输入模板名称'); return }
  if (!form.value.code?.trim()) { message.error('请输入模板代码'); return }
  if (!form.value.base_template) { message.error('请选择基础模板'); return }

  // 校验 JSON 格式字段
  for (const field of ['default_list_rule', 'default_detail_rule', 'default_anti_bot']) {
    if (form.value[field]?.trim()) {
      try { JSON.parse(form.value[field]) }
      catch { message.error(`${field} JSON 格式错误`); return }
    }
  }

  saving.value = true
  try {
    const payload = { ...form.value }
    if (editingId.value) {
      await request.put(`/api/custom-templates/${editingId.value}`, payload)
      message.success('模板已更新')
    } else {
      await request.post('/api/custom-templates', payload)
      message.success('自定义模板已创建')
    }
    modalVisible.value = false
    fetchCustomTemplates()
  } catch (e) {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

async function onDeleteCustom(id) {
  try {
    await request.delete(`/api/custom-templates/${id}`)
    message.success('模板已删除')
    fetchCustomTemplates()
  } catch {
    // handled
  }
}

async function fetchBuiltinData() {
  try {
    const healthRaw = await request.get('/api/monitor/templates')
    const healthList = Array.isArray(healthRaw) ? healthRaw : []
    const healthMap = {}
    for (const h of healthList) healthMap[h.template] = h

    const sourceRes = await request.get('/api/sources/statistics')
    const templateCounts = sourceRes?.template_counts || sourceRes?.templateCounts || {}

    builtinTemplates.value = BASE_TEMPLATES.map(t => {
      const h = healthMap[t.code] || {}
      return { ...t, sourceCount: templateCounts[t.code] || 0, taskTotal: h.total || 0, rate: h.successRate ?? h.success_rate ?? 0 }
    })
  } catch { /* ignore */ }
}

async function fetchCustomTemplates() {
  try {
    const data = await request.get('/api/custom-templates')
    customTemplates.value = Array.isArray(data) ? data : []
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchBuiltinData()
  fetchCustomTemplates()
})
</script>
