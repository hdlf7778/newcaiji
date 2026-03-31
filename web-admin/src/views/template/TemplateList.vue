<!--
  模板列表页（TemplateList）— 列表模式 + 点击查看采集源
-->
<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">模板列表</h2>
      <a-button type="primary" @click="onAddCustom">
        <template #icon><PlusOutlined /></template>
        添加自定义模板
      </a-button>
    </div>

    <a-row :gutter="16">
      <!-- 左侧：模板表格 -->
      <a-col :span="selectedTemplate ? 10 : 24">
        <!-- 内置模板 -->
        <a-card title="内置模板" size="small" style="margin-bottom:16px;">
          <a-table
            :columns="builtinColumns"
            :data-source="builtinTemplates"
            :pagination="false"
            row-key="code"
            size="small"
            :row-class-name="(record) => record.code === selectedTemplate?.code ? 'row-selected' : ''"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <a @click="onSelectTemplate(record, 'builtin')" style="display:flex;align-items:center;gap:6px;">
                  <a-tag :color="record.color" size="small">{{ record.letter }}</a-tag>
                  <span style="font-weight:500;">{{ record.label }}</span>
                </a>
              </template>
              <template v-if="column.key === 'queue'">
                <a-tag :color="record.queue === 'http' ? 'blue' : 'orange'" size="small">{{ record.queue.toUpperCase() }}</a-tag>
              </template>
              <template v-if="column.key === 'rate'">
                <span :style="{ color: record.rate >= 95 ? '#52c41a' : record.rate >= 80 ? '#fa8c16' : '#ff4d4f' }">
                  {{ record.rate }}%
                </span>
              </template>
              <template v-if="column.key === 'builtin_action'">
                <router-link :to="'/templates/' + record.code">
                  <a-button type="link" size="small">详情</a-button>
                </router-link>
              </template>
            </template>
          </a-table>
        </a-card>

        <!-- 自定义模板 -->
        <a-card size="small">
          <template #title>
            <span>自定义模板 <a-tag size="small">{{ customTemplates.length }}</a-tag></span>
          </template>
          <a-table
            :columns="customColumns"
            :data-source="customTemplates"
            :pagination="customTemplates.length > 20 ? { pageSize: 20, size: 'small' } : false"
            row-key="id"
            size="small"
            :row-class-name="(record) => record.id === selectedTemplate?.id && selectedType === 'custom' ? 'row-selected' : ''"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <a @click="onSelectTemplate(record, 'custom')" style="font-weight:500;">{{ record.name }}</a>
              </template>
              <template v-if="column.key === 'base_template'">
                <a-tag size="small">{{ baseTemplateLabel(record.base_template) }}</a-tag>
              </template>
              <template v-if="column.key === 'enabled'">
                <a-tag :color="record.enabled ? 'green' : 'default'" size="small">{{ record.enabled ? '启用' : '停用' }}</a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-space>
                  <router-link :to="'/templates/' + record.id">
                    <a-button type="link" size="small">详情</a-button>
                  </router-link>
                  <a-button type="link" size="small" @click.stop="onEditCustom(record)">编辑</a-button>
                  <a-popconfirm title="确认删除此模板？" @confirm="onDeleteCustom(record.id)">
                    <a-button type="link" size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
            <template #emptyText>
              <div style="padding:16px;text-align:center;color:#8c8c8c;">暂无自定义模板</div>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <!-- 右侧：选中模板的采集源列表 -->
      <a-col v-if="selectedTemplate" :span="14">
        <a-card size="small">
          <template #title>
            <div style="display:flex;align-items:center;gap:8px;">
              <a-tag v-if="selectedTemplate.letter" :color="selectedTemplate.color">{{ selectedTemplate.letter }}</a-tag>
              <a-tag v-else color="purple">自定义</a-tag>
              <span>{{ selectedTemplate.label || selectedTemplate.name }}</span>
              <span style="color:#8c8c8c;font-size:13px;">的采集源</span>
              <a-tag>{{ sourcePagination.total }} 个</a-tag>
            </div>
          </template>
          <template #extra>
            <a-button type="text" size="small" @click="selectedTemplate = null">关闭</a-button>
          </template>

          <div v-if="selectedTemplate.desc || selectedTemplate.description" style="margin-bottom:12px;font-size:12px;color:#8c8c8c;">
            {{ selectedTemplate.desc || selectedTemplate.description }}
          </div>

          <a-spin :spinning="sourceListLoading">
            <a-table
              :columns="sourceColumns"
              :data-source="sourceList"
              :pagination="sourcePagination.total > 20 ? { ...sourcePagination, size: 'small', showSizeChanger: false } : false"
              row-key="id"
              size="small"
              @change="onSourcePageChange"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'name'">
                  <router-link :to="'/sources/' + record.id">{{ record.name }}</router-link>
                </template>
                <template v-if="column.key === 'status'">
                  <a-tag :color="statusColor(record.status)" size="small">{{ statusLabel(record.status) }}</a-tag>
                </template>
                <template v-if="column.key === 'trial_score'">
                  {{ record.trial_score != null ? record.trial_score : '—' }}
                </template>
                <template v-if="column.key === 'health_score'">
                  <span :style="{ color: (record.health_score ?? 100) >= 80 ? '#52c41a' : (record.health_score ?? 100) >= 50 ? '#fa8c16' : '#ff4d4f' }">
                    {{ record.health_score ?? '—' }}
                  </span>
                </template>
              </template>
              <template #emptyText>
                <div style="padding:24px;text-align:center;color:#8c8c8c;">暂无采集源使用此模板</div>
              </template>
            </a-table>
          </a-spin>
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
        </a-form-item>
        <a-form-item label="模板说明">
          <a-textarea v-model:value="form.description" placeholder="描述此模板适用的场景" :rows="2" />
        </a-form-item>
        <a-form-item label="默认列表规则">
          <a-textarea v-model:value="form.default_list_rule" :rows="4" style="font-family:monospace;font-size:12px;"
            placeholder='{"list_container": "ul", "title_selector": "a", ...}' />
        </a-form-item>
        <a-form-item label="默认详情规则">
          <a-textarea v-model:value="form.default_detail_rule" :rows="4" style="font-family:monospace;font-size:12px;"
            placeholder='{"content_selector": ".article-content", "title_selector": "h1", ...}' />
        </a-form-item>
        <a-form-item label="默认反爬配置">
          <a-textarea v-model:value="form.default_anti_bot" :rows="3" style="font-family:monospace;font-size:12px;"
            placeholder='{"type": "cookie_auto", "delay_min": 1, "delay_max": 3}' />
        </a-form-item>
        <a-form-item label="启用状态">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import request from '../../api/request.js'
import { statusLabel, statusColor } from '../../constants/source.js'

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

// 内置模板列
const builtinColumns = [
  { title: '模板', key: 'name', width: 170 },
  { title: '说明', dataIndex: 'desc', key: 'desc', ellipsis: true },
  { title: '队列', key: 'queue', width: 80, align: 'center' },
  { title: '采集源', dataIndex: 'sourceCount', key: 'sourceCount', width: 80, align: 'center' },
  { title: '24h任务', dataIndex: 'taskTotal', key: 'taskTotal', width: 80, align: 'center' },
  { title: '成功率', key: 'rate', width: 80, align: 'center' },
  { title: '', key: 'builtin_action', width: 60, align: 'center' },
]

// 自定义模板列
const customColumns = [
  { title: '名称', key: 'name', width: 160 },
  { title: '代码', dataIndex: 'code', key: 'code', width: 130 },
  { title: '基础模板', key: 'base_template', width: 120 },
  { title: '采集源', dataIndex: 'source_count', key: 'source_count', width: 70, align: 'center' },
  { title: '状态', key: 'enabled', width: 70, align: 'center' },
  { title: '操作', key: 'action', width: 110, align: 'center' },
]

// 采集源列
const sourceColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '名称', key: 'name', ellipsis: true },
  { title: '状态', key: 'status', width: 100 },
  { title: '评分', key: 'trial_score', width: 70, align: 'center' },
  { title: '健康度', key: 'health_score', width: 80, align: 'center' },
  { title: '地区', dataIndex: 'region', key: 'region', width: 100, ellipsis: true },
]

// State
const builtinTemplates = ref(BASE_TEMPLATES.map(t => ({ ...t, sourceCount: 0, taskTotal: 0, rate: 0 })))
const customTemplates = ref([])

// 右侧面板
const selectedTemplate = ref(null)
const selectedType = ref('')
const sourceList = ref([])
const sourceListLoading = ref(false)
const sourcePagination = reactive({ current: 1, pageSize: 20, total: 0 })

// Modal
const modalVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const form = ref(makeEmptyForm())

function makeEmptyForm() {
  return { name: '', code: '', base_template: '', description: '', default_list_rule: '', default_detail_rule: '', default_anti_bot: '', enabled: true }
}

function baseTemplateLabel(code) {
  const bt = BASE_TEMPLATES.find(t => t.code === code)
  return bt ? `${bt.letter} ${bt.label}` : code || '\u2014'
}

// 点击模板名 → 加载右侧采集源
async function onSelectTemplate(tpl, type) {
  selectedTemplate.value = tpl
  selectedType.value = type
  sourcePagination.current = 1
  await loadSources()
}

async function loadSources() {
  const tpl = selectedTemplate.value
  if (!tpl) return
  sourceListLoading.value = true
  try {
    const templateCode = selectedType.value === 'builtin' ? tpl.code : tpl.base_template
    const res = await request.get('/api/sources', {
      params: { template: templateCode, page: sourcePagination.current, pageSize: sourcePagination.pageSize }
    })
    sourceList.value = res?.records || []
    sourcePagination.total = res?.total || 0
  } catch {
    sourceList.value = []
  } finally {
    sourceListLoading.value = false
  }
}

function onSourcePageChange(pag) {
  sourcePagination.current = pag.current
  loadSources()
}

// CRUD
function onAddCustom() {
  editingId.value = null
  form.value = makeEmptyForm()
  modalVisible.value = true
}

function onEditCustom(ct) {
  editingId.value = ct.id
  form.value = {
    name: ct.name, code: ct.code, base_template: ct.base_template,
    description: ct.description || '',
    default_list_rule: ct.default_list_rule || '',
    default_detail_rule: ct.default_detail_rule || '',
    default_anti_bot: ct.default_anti_bot || '',
    enabled: ct.enabled !== false,
  }
  modalVisible.value = true
}

async function onSave() {
  if (!form.value.name?.trim()) { message.error('请输入模板名称'); return }
  if (!form.value.code?.trim()) { message.error('请输入模板代码'); return }
  if (!form.value.base_template) { message.error('请选择基础模板'); return }
  for (const field of ['default_list_rule', 'default_detail_rule', 'default_anti_bot']) {
    if (form.value[field]?.trim()) {
      try { JSON.parse(form.value[field]) }
      catch { message.error(`${field} JSON 格式错误`); return }
    }
  }
  saving.value = true
  try {
    if (editingId.value) {
      await request.put(`/api/custom-templates/${editingId.value}`, form.value)
      message.success('模板已更新')
    } else {
      await request.post('/api/custom-templates', form.value)
      message.success('自定义模板已创建')
    }
    modalVisible.value = false
    fetchCustomTemplates()
  } catch { /* handled */ } finally {
    saving.value = false
  }
}

async function onDeleteCustom(id) {
  try {
    await request.delete(`/api/custom-templates/${id}`)
    message.success('模板已删除')
    if (selectedTemplate.value?.id === id) selectedTemplate.value = null
    fetchCustomTemplates()
  } catch { /* handled */ }
}

// Data fetching
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

<style scoped>
:deep(.row-selected) {
  background-color: #e6f4ff !important;
}
:deep(.row-selected td) {
  background-color: #e6f4ff !important;
}
</style>
