<!--
  文章列表页（ArticleList）

  功能：
    - 筛选：来源网站名称、地区、发布时间范围、关键词
    - 导出 CSV：优先调用后端导出接口，失败时降级为客户端当前页导出
    - 点击标题跳转到文章详情页
-->
<template>
  <div>
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">文章列表</h2>
      <a-button :loading="exportLoading" @click="onExport">
        📥 导出CSV
      </a-button>
    </div>

    <!-- Filter bar -->
    <a-card style="margin-bottom:16px;" :body-style="{ padding: '12px 16px' }">
      <a-space wrap>
        <a-space>
          <span style="font-size:13px;color:#595959;">来源网站</span>
          <a-input
            v-model:value="query.sourceName"
            placeholder="输入网站名称"
            style="width:160px;"
            allow-clear
            @pressEnter="onSearch"
          />
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">地区</span>
          <a-select v-model:value="query.region" style="width:130px;" @change="onFilterChange">
            <a-select-option value="">全部</a-select-option>
            <a-select-option value="浙江">浙江</a-select-option>
            <a-select-option value="黑龙江">黑龙江</a-select-option>
            <a-select-option value="福建">福建</a-select-option>
            <a-select-option value="湖南">湖南</a-select-option>
            <a-select-option value="广东">广东</a-select-option>
            <a-select-option value="湖北">湖北</a-select-option>
            <a-select-option value="江苏">江苏</a-select-option>
          </a-select>
        </a-space>
        <a-space>
          <span style="font-size:13px;color:#595959;">发布时间</span>
          <a-range-picker
            v-model:value="dateRange"
            style="width:240px;"
            @change="onFilterChange"
          />
        </a-space>
        <a-input-search
          v-model:value="query.keyword"
          placeholder="标题/正文关键词..."
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
        row-key="id"
        size="middle"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'title'">
            <router-link :to="`/articles/${record.id}`" style="color:#1677ff;">
              {{ record.title }}
            </router-link>
          </template>
          <template v-if="column.key === 'url'">
            <a :href="record.url" target="_blank" style="color:#1677ff;">
              <LinkOutlined />
            </a>
          </template>
          <template v-if="column.key === 'source_name'">
            <router-link v-if="sourceInfoMap[record.source_id]" :to="`/sources/${record.source_id}`" style="color:#1677ff;">
              {{ sourceInfoMap[record.source_id]?.name }}
            </router-link>
            <span v-else style="color:#bfbfbf;">#{{ record.source_id }}</span>
          </template>
          <template v-if="column.key === 'column_name'">
            {{ sourceInfoMap[record.source_id]?.column_name || '—' }}
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { LinkOutlined } from '@ant-design/icons-vue'
import { articleApi } from '../../api/article.js'
import request from '../../api/request.js'

const query = reactive({
  sourceName: '',
  region: '',
  keyword: '',
  page: 1,
  pageSize: 20,
})

const dateRange = ref([])
const tableData = ref([])
const loading = ref(false)
const exportLoading = ref(false)
const total = ref(0)

const pagination = computed(() => ({
  current: query.page,
  pageSize: query.pageSize,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t) => `共 ${t} 条`,
}))

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title', width: 280, ellipsis: true },
  { title: '网址', dataIndex: 'url', key: 'url', width: 50 },
  { title: '网站名称', dataIndex: 'source_id', key: 'source_name', width: 130 },
  { title: '栏目名称', dataIndex: 'source_id', key: 'column_name', width: 120 },
  { title: '发布时间', dataIndex: 'publish_date', key: 'publish_date', width: 110 },
  { title: '采集时间', dataIndex: 'fetched_at', key: 'fetched_at', width: 150 },
]

// 采集源信息缓存：{id: {name, column_name}}
const sourceInfoMap = ref({})
async function loadSourceInfo() {
  try {
    const res = await request.get('/api/sources', { params: { page: 1, pageSize: 500 } })
    for (const s of (res?.records || [])) {
      sourceInfoMap.value[s.id] = { name: s.name, column_name: s.column_name }
    }
  } catch { /* ignore */ }
}

async function fetchList() {
  loading.value = true
  try {
    const params = {}
    if (query.sourceName) params.sourceName = query.sourceName
    if (query.region) params.region = query.region
    if (query.keyword) params.keyword = query.keyword
    if (dateRange.value && dateRange.value.length === 2) {
      params.startDate = dateRange.value[0]?.format?.('YYYY-MM-DD') || dateRange.value[0]
      params.endDate = dateRange.value[1]?.format?.('YYYY-MM-DD') || dateRange.value[1]
    }
    params.page = query.page
    params.pageSize = query.pageSize
    const res = await articleApi.list(params)
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

/**
 * 导出文章为 CSV
 * 优先调用后端 /api/articles/export（全量数据）；
 * 后端失败时 fallback 到前端拼接当前页数据（仅当前页，存在数据不全问题）
 */
async function onExport() {
  exportLoading.value = true
  try {
    const params = {}
    if (query.sourceName) params.sourceName = query.sourceName
    if (query.region) params.region = query.region
    if (query.keyword) params.keyword = query.keyword
    if (dateRange.value && dateRange.value.length === 2) {
      params.startDate = dateRange.value[0]?.format?.('YYYY-MM-DD') || dateRange.value[0]
      params.endDate = dateRange.value[1]?.format?.('YYYY-MM-DD') || dateRange.value[1]
    }

    try {
      const blob = await articleApi.export(params)
      const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]))
      const a = document.createElement('a')
      a.href = url
      a.download = `articles_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
      message.success('导出成功')
    } catch {
      // fallback: client-side export
      const headers = ['网站名称', '栏目名称', '文章网址', '标题', '发布时间', '正文内容']
      const rows = tableData.value.map((r) => [
        r.sourceName || '',
        r.columnName || '',
        r.url || '',
        r.title || '',
        r.publishTime || '',
        (r.content || '').replace(/\n/g, ' '),
      ])
      const csv = [headers, ...rows]
        .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\n')
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `articles_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
      message.success('导出成功（当前页数据）')
    }
  } finally {
    exportLoading.value = false
  }
}

onMounted(() => {
  loadSourceInfo()
  fetchList()
})
</script>
