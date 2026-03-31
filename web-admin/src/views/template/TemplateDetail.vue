<!--
  模板详情页 — 展示内置模板或自定义模板的完整配置、规则、说明
  路由: /templates/:id (id 为内置模板 code 如 static_list，或自定义模板数字 id)
-->
<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">
        <router-link to="/templates" style="color:#8c8c8c;font-weight:400;">模板列表</router-link>
        <span style="margin:0 8px;color:#d9d9d9;">/</span>
        {{ templateData?.label || templateData?.name || '模板详情' }}
      </h2>
      <a-space>
        <router-link to="/templates"><a-button>返回列表</a-button></router-link>
        <a-button v-if="isCustom" type="primary" @click="onEdit">编辑</a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <a-row :gutter="16" v-if="templateData">
        <!-- 左侧：基本信息 + 配置 -->
        <a-col :span="16">
          <!-- 基本信息 -->
          <a-card title="基本信息" size="small" style="margin-bottom:16px;">
            <a-descriptions :column="2" size="small" bordered>
              <a-descriptions-item label="模板名称">
                <div style="display:flex;align-items:center;gap:8px;">
                  <a-tag v-if="templateData.letter" :color="templateData.color">{{ templateData.letter }}</a-tag>
                  <a-tag v-else color="purple">自定义</a-tag>
                  <span style="font-weight:500;">{{ templateData.label || templateData.name }}</span>
                </div>
              </a-descriptions-item>
              <a-descriptions-item label="模板代码">
                <code style="background:#f5f5f5;padding:2px 8px;border-radius:3px;">{{ templateData.code }}</code>
              </a-descriptions-item>
              <a-descriptions-item label="采集队列">
                <a-tag :color="queueType === 'http' ? 'blue' : 'orange'">{{ queueType.toUpperCase() }}</a-tag>
                <span style="color:#8c8c8c;font-size:12px;margin-left:4px;">
                  {{ queueType === 'http' ? '使用 httpx 轻量客户端' : '使用 Playwright 无头浏览器' }}
                </span>
              </a-descriptions-item>
              <a-descriptions-item label="采集源数量">
                <span style="font-weight:600;font-size:16px;">{{ sourceCount }}</span> 个
              </a-descriptions-item>
              <a-descriptions-item v-if="isCustom" label="基础模板">
                <a-tag>{{ baseTemplateLabel(templateData.base_template) }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item v-if="isCustom" label="状态">
                <a-tag :color="templateData.enabled ? 'green' : 'default'">{{ templateData.enabled ? '启用' : '停用' }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="说明" :span="2">
                {{ templateData.desc || templateData.description || '暂无说明' }}
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <!-- 采集能力说明（内置模板） -->
          <a-card v-if="!isCustom" title="采集能力" size="small" style="margin-bottom:16px;">
            <div v-html="capabilityHtml" style="font-size:13px;line-height:1.8;color:#595959;"></div>
          </a-card>

          <!-- 规则配置（自定义模板） -->
          <a-card v-if="isCustom" title="默认规则配置" size="small" style="margin-bottom:16px;">
            <a-tabs size="small">
              <a-tab-pane key="list" tab="列表规则">
                <pre v-if="templateData.default_list_rule" style="background:#fafafa;padding:12px;border-radius:4px;font-size:12px;max-height:300px;overflow:auto;">{{ formatJson(templateData.default_list_rule) }}</pre>
                <a-empty v-else description="未配置默认列表规则" :image-style="{ height: '40px' }" />
              </a-tab-pane>
              <a-tab-pane key="detail" tab="详情规则">
                <pre v-if="templateData.default_detail_rule" style="background:#fafafa;padding:12px;border-radius:4px;font-size:12px;max-height:300px;overflow:auto;">{{ formatJson(templateData.default_detail_rule) }}</pre>
                <a-empty v-else description="未配置默认详情规则" :image-style="{ height: '40px' }" />
              </a-tab-pane>
              <a-tab-pane key="antibot" tab="反爬配置">
                <pre v-if="templateData.default_anti_bot" style="background:#fafafa;padding:12px;border-radius:4px;font-size:12px;max-height:300px;overflow:auto;">{{ formatJson(templateData.default_anti_bot) }}</pre>
                <a-empty v-else description="未配置默认反爬策略" :image-style="{ height: '40px' }" />
              </a-tab-pane>
            </a-tabs>
          </a-card>

          <!-- 默认规则参考（内置模板） -->
          <a-card v-if="!isCustom" title="默认规则参考" size="small">
            <a-tabs size="small">
              <a-tab-pane key="list" tab="列表规则">
                <pre style="background:#fafafa;padding:12px;border-radius:4px;font-size:12px;max-height:300px;overflow:auto;">{{ formatJson(builtinRules.list_rule) }}</pre>
              </a-tab-pane>
              <a-tab-pane key="detail" tab="详情规则">
                <pre style="background:#fafafa;padding:12px;border-radius:4px;font-size:12px;max-height:300px;overflow:auto;">{{ formatJson(builtinRules.detail_rule) }}</pre>
              </a-tab-pane>
            </a-tabs>
          </a-card>
        </a-col>

        <!-- 右侧：采集源列表 -->
        <a-col :span="8">
          <a-card size="small">
            <template #title>
              使用此模板的采集源 <a-tag size="small">{{ sourceCount }}</a-tag>
            </template>
            <a-spin :spinning="sourceLoading">
              <div v-for="src in sourceList" :key="src.id" style="padding:6px 0;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                <div style="flex:1;min-width:0;">
                  <router-link :to="'/sources/' + src.id" style="font-size:13px;">{{ src.name }}</router-link>
                  <div style="font-size:11px;color:#8c8c8c;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ src.region || '' }}</div>
                </div>
                <a-tag :color="statusColor(src.status)" size="small" style="flex-shrink:0;">{{ statusLabel(src.status) }}</a-tag>
              </div>
              <div v-if="!sourceList.length && !sourceLoading" style="padding:20px;text-align:center;color:#8c8c8c;font-size:13px;">
                暂无采集源
              </div>
              <div v-if="sourceCount > sourceList.length" style="padding:8px 0;text-align:center;">
                <a-button type="link" size="small" @click="loadMoreSources">加载更多...</a-button>
              </div>
            </a-spin>
          </a-card>
        </a-col>
      </a-row>
    </a-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import request from '../../api/request.js'
import { statusLabel, statusColor } from '../../constants/source.js'

const route = useRoute()
const router = useRouter()

const BASE_TEMPLATES = [
  { code: 'static_list',        letter: 'A', label: '静态列表页',  queue: 'http',    color: 'purple', desc: '最常见的采集模板。适用于服务端渲染的 HTML 列表页，通过 CSS 选择器提取文章标题、链接、日期。支持分页翻页和自定义提取规则。' },
  { code: 'iframe_loader',      letter: 'B', label: 'iframe加载', queue: 'browser',  color: 'orange', desc: '适用于内容嵌套在 iframe 中的页面。自动检测 iframe src 地址，进入 iframe 后按标准 HTML 方式提取内容。需要 Browser Worker。' },
  { code: 'api_json',           letter: 'C', label: 'API接口型',  queue: 'http',    color: 'blue',   desc: '适用于前后端分离的站点。直接调用 JSON API 获取结构化数据，无需解析 HTML。需要配置 API 地址、请求方法和 JSON 字段路径。' },
  { code: 'wechat_article',     letter: 'D', label: '微信公众号',  queue: 'http',    color: 'green',  desc: '适用于微信公众号文章。使用特殊的 User-Agent 和选择器适配微信文章页面结构，支持提取正文、图片和发布时间。' },
  { code: 'search_discovery',   letter: 'E', label: '搜索监控',   queue: 'http',    color: 'cyan',   desc: '适用于搜索引擎结果页监控。定期搜索指定关键词，采集搜索结果中的新增链接和摘要。' },
  { code: 'auth_required',      letter: 'F', label: '登录态采集',  queue: 'browser',  color: 'red',    desc: '适用于需要登录后才能访问的站点。通过 Playwright 模拟登录流程，维持登录态后采集。需要 Browser Worker 和登录凭据配置。' },
  { code: 'spa_render',         letter: 'G', label: 'SPA渲染',   queue: 'browser',  color: 'volcano', desc: '适用于 Vue/React 等单页应用。使用 Playwright 渲染 JavaScript 后提取内容。适合页面 HTML 为空壳、内容由 JS 动态加载的站点。需要 Browser Worker。' },
  { code: 'rss_feed',           letter: 'H', label: 'RSS订阅',   queue: 'http',    color: 'lime',   desc: '适用于提供 RSS/Atom 订阅源的站点。直接解析 XML feed 获取文章列表，效率高、不触发反爬。' },
  { code: 'gov_cloud_platform', letter: 'I', label: '政务云平台',  queue: 'http',    color: 'geekblue', desc: '适用于政府统一建站平台（JCMS、JPAAS 等）。采用多策略适配：先尝试 CSS 选择器，再用标准政务 HTML 提取，最后 fallback 到 JCMS API。覆盖率最高（36.8%）。' },
  { code: 'captured_api',       letter: 'J', label: '抓包API',   queue: 'http',    color: 'default', desc: '适用于通过浏览器抓包发现的隐藏 API。配置方式类似 API 接口型，但通常需要特殊的请求头、Cookie 或签名参数。' },
]

const BUILTIN_RULES = {
  static_list: {
    list_rule: { list_container: 'ul, .list, .news-list', list_item: 'li, .item', title_selector: 'a', url_selector: 'a[href]', date_selector: 'span, .date, .time', max_items: 20 },
    detail_rule: { title_selector: 'h1, h2.title', content_selector: '.content, .article-content, .TRS_Editor', publish_time_selector: 'span.time, .publish-date', remove_selectors: ['script', 'style', '.share-bar', 'nav', 'footer'] },
  },
  iframe_loader: {
    list_rule: { iframe_selector: 'iframe[src]', title_selector: 'a', url_selector: 'a[href]' },
    detail_rule: { title_selector: 'h1', content_selector: '.content, .main', remove_selectors: ['script', 'style'] },
  },
  api_json: {
    list_rule: { api_url: '/api/articles/list', api_method: 'GET', api_params: { page: 1, pageSize: 20 }, data_path: 'data.records', title_field: 'title', url_field: 'url', date_field: 'publishDate' },
    detail_rule: { title_selector: 'h1', content_selector: '.article-content', remove_selectors: ['script', 'style'] },
  },
  wechat_article: {
    list_rule: { title_selector: '.weui_media_title', url_selector: '.weui_media_title', date_selector: '.weui_media_extra_info' },
    detail_rule: { title_selector: '#activity-name', content_selector: '#js_content', publish_time_selector: '#publish_time', remove_selectors: ['script', 'style', '.qr_code_pc'] },
  },
  search_discovery: {
    list_rule: { search_engine: 'baidu', keywords: '', title_selector: 'h3 a', url_selector: 'h3 a[href]' },
    detail_rule: { title_selector: 'h1', content_selector: '.content' },
  },
  auth_required: {
    list_rule: { login_url: '', username_selector: '#username', password_selector: '#password', submit_selector: '#login-btn', title_selector: 'a', url_selector: 'a[href]' },
    detail_rule: { title_selector: 'h1', content_selector: '.content' },
  },
  spa_render: {
    list_rule: { wait_selector: '.list-loaded, [data-loaded]', wait_timeout: 10000, title_selector: 'a', url_selector: 'a[href]' },
    detail_rule: { wait_selector: '.article-content', title_selector: 'h1', content_selector: '.article-content', remove_selectors: ['script', 'style', 'nav'] },
  },
  rss_feed: {
    list_rule: { feed_url: '', title_field: 'title', url_field: 'link', date_field: 'published' },
    detail_rule: { title_selector: 'h1', content_selector: '.content, .entry-content', remove_selectors: ['script', 'style'] },
  },
  gov_cloud_platform: {
    list_rule: { strategy: 'auto', list_container: 'auto', title_selector: 'a', url_selector: 'a[href]', fallback: 'jcms_api', max_items: 20 },
    detail_rule: { title_selector: 'h1, h2.Article-title', content_selector: '.TRS_Editor, .article, .bt_content, .content', publish_time_selector: '.ly span, span.time', remove_selectors: ['script', 'style', '.share-bar', 'nav', 'footer'] },
  },
  captured_api: {
    list_rule: { api_url: '', api_method: 'GET', headers: {}, api_params: {}, data_path: 'data', title_field: 'title', url_field: 'url' },
    detail_rule: { title_selector: 'h1', content_selector: '.content', remove_selectors: ['script', 'style'] },
  },
}

const CAPABILITY_DESCRIPTIONS = {
  static_list: '<strong>采集策略：</strong>CSS 选择器提取<br/><strong>支持功能：</strong>列表页分页、日期过滤、增量采集、自定义选择器<br/><strong>适用场景：</strong>传统服务端渲染网站（PHP/Java/Python 等后端直出 HTML）<br/><strong>性能：</strong>高并发，单次请求约 50-200ms',
  iframe_loader: '<strong>采集策略：</strong>自动检测 iframe → 进入 iframe → HTML 提取<br/><strong>支持功能：</strong>嵌套 iframe 解析、跨域 iframe 处理<br/><strong>适用场景：</strong>将内容嵌入 iframe 展示的政府/企业网站<br/><strong>性能：</strong>需要 Browser Worker，单次约 2-5s',
  api_json: '<strong>采集策略：</strong>直接调用 REST/JSON API<br/><strong>支持功能：</strong>GET/POST 请求、自定义 Headers、JSON 路径提取、分页参数<br/><strong>适用场景：</strong>前后端分离架构、移动端 H5 页面、SPA 网站的底层 API<br/><strong>性能：</strong>最快，无需解析 HTML，单次约 20-100ms',
  wechat_article: '<strong>采集策略：</strong>微信专用 UA + 选择器<br/><strong>支持功能：</strong>公众号文章正文、图片、发布时间提取<br/><strong>适用场景：</strong>微信公众号文章页面<br/><strong>性能：</strong>中等，需处理微信反爬',
  search_discovery: '<strong>采集策略：</strong>搜索引擎结果页解析<br/><strong>支持功能：</strong>关键词搜索、结果去重、新增发现<br/><strong>适用场景：</strong>监控特定关键词在搜索引擎中的新出现内容<br/><strong>性能：</strong>中等',
  auth_required: '<strong>采集策略：</strong>Playwright 模拟登录 → Cookie 维持 → 常规提取<br/><strong>支持功能：</strong>表单登录、Cookie 持久化、登录态检测和自动重新登录<br/><strong>适用场景：</strong>需要账号密码登录后才能访问内容的网站<br/><strong>性能：</strong>较慢，需要 Browser Worker，首次登录约 5-10s',
  spa_render: '<strong>采集策略：</strong>Playwright 渲染 JS → 等待内容加载 → CSS 选择器提取<br/><strong>支持功能：</strong>等待特定元素出现、滚动加载、JS 执行<br/><strong>适用场景：</strong>Vue/React/Angular 等前端框架构建的 SPA 网站<br/><strong>性能：</strong>较慢，需要 Browser Worker，单次约 3-8s',
  rss_feed: '<strong>采集策略：</strong>XML 解析 RSS/Atom feed<br/><strong>支持功能：</strong>标准 RSS 2.0 和 Atom 格式、CDATA 正文提取<br/><strong>适用场景：</strong>提供 RSS 订阅的新闻/博客/政府网站<br/><strong>性能：</strong>最快，无反爬风险，单次约 10-50ms',
  gov_cloud_platform: '<strong>采集策略：</strong>多策略自动适配（CSS 选择器 → 标准政务 HTML → JCMS API）<br/><strong>支持功能：</strong>自动识别子类型（JCMS col、标准 HTML、信息公开平台）、unitId API 调用<br/><strong>适用场景：</strong>省级统一政务云平台建设的政府网站（覆盖率 36.8%）<br/><strong>性能：</strong>中等，多策略 fallback 可能增加延迟',
  captured_api: '<strong>采集策略：</strong>调用抓包发现的隐藏 API<br/><strong>支持功能：</strong>自定义请求头、Cookie、签名参数、POST body<br/><strong>适用场景：</strong>通过浏览器 F12 抓包发现的非公开 API 接口<br/><strong>性能：</strong>快，类似 API 接口型',
}

// State
const loading = ref(false)
const templateData = ref(null)
const isCustom = ref(false)
const sourceList = ref([])
const sourceLoading = ref(false)
const sourceCount = ref(0)
let sourcePage = 1

const queueType = computed(() => {
  if (templateData.value?.queue) return templateData.value.queue
  const base = BASE_TEMPLATES.find(t => t.code === templateData.value?.base_template)
  return base?.queue || 'http'
})

const builtinRules = computed(() => {
  const code = templateData.value?.code
  return BUILTIN_RULES[code] || { list_rule: {}, detail_rule: {} }
})

const capabilityHtml = computed(() => {
  return CAPABILITY_DESCRIPTIONS[templateData.value?.code] || ''
})

function baseTemplateLabel(code) {
  const bt = BASE_TEMPLATES.find(t => t.code === code)
  return bt ? `${bt.letter} ${bt.label}` : code || '\u2014'
}

function formatJson(data) {
  if (!data) return '{}'
  if (typeof data === 'string') {
    try { return JSON.stringify(JSON.parse(data), null, 2) }
    catch { return data }
  }
  return JSON.stringify(data, null, 2)
}

async function loadTemplate() {
  loading.value = true
  const id = route.params.id

  // Check if it's a builtin template code
  const builtin = BASE_TEMPLATES.find(t => t.code === id)
  if (builtin) {
    templateData.value = { ...builtin }
    isCustom.value = false
    loading.value = false
    await loadSources(builtin.code)
    return
  }

  // Otherwise load custom template by ID
  try {
    const data = await request.get(`/api/custom-templates/${id}`)
    templateData.value = data
    isCustom.value = true
    await loadSources(data.base_template)
  } catch {
    message.error('模板不存在')
    router.push('/templates')
  } finally {
    loading.value = false
  }
}

async function loadSources(templateCode) {
  sourceLoading.value = true
  try {
    const res = await request.get('/api/sources', {
      params: { template: templateCode, page: 1, pageSize: 50 }
    })
    sourceList.value = res?.records || []
    sourceCount.value = res?.total || 0
    sourcePage = 1
  } catch {
    sourceList.value = []
  } finally {
    sourceLoading.value = false
  }
}

async function loadMoreSources() {
  sourcePage++
  const templateCode = isCustom.value ? templateData.value?.base_template : templateData.value?.code
  sourceLoading.value = true
  try {
    const res = await request.get('/api/sources', {
      params: { template: templateCode, page: sourcePage, pageSize: 50 }
    })
    const more = res?.records || []
    sourceList.value = [...sourceList.value, ...more]
  } catch { /* ignore */ } finally {
    sourceLoading.value = false
  }
}

function onEdit() {
  router.push(`/templates/${route.params.id}?edit=1`)
}

onMounted(loadTemplate)
</script>
