<!--
  规则列表页（RuleList）

  功能：
    - 展示所有采集规则，支持按模板类型和关键词筛选
    - 采集源名称通过额外请求加载（sourceNameMap 缓存）
    - 支持编辑和删除操作
-->
<template>
  <div>
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">规则配置</h2>
    </div>

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
        <a-input-search
          v-model:value="query.keyword"
          placeholder="搜索采集源名称..."
          style="width:240px;"
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
          <template v-if="column.key === 'source_name'">
            <router-link :to="`/sources/${record.source_id}`" style="color:#1677ff;">
              {{ sourceInfoMap[record.source_id]?.name || `#${record.source_id}` }}
            </router-link>
          </template>
          <template v-if="column.key === 'column_name'">
            {{ sourceInfoMap[record.source_id]?.column_name || '—' }}
          </template>
          <template v-if="column.key === 'generated_by'">
            <a-tag :color="genModeColor(record.generated_by)">
              {{ genModeLabel(record.generated_by) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <a-space>
              <router-link :to="`/rules/${record.id}/edit`">
                <a-button type="link" size="small">编辑</a-button>
              </router-link>
              <a-button type="link" size="small" danger @click="onDelete(record)">删除</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import request from '../../api/request.js'
import { message, Modal } from 'ant-design-vue'
import { ruleApi } from '../../api/rule.js'
import { useSourceInfo } from '../../composables/useSourceInfo.js'

const query = reactive({
  templateType: '',
  keyword: '',
  page: 1,
  pageSize: 20,
})

const tableData = ref([])
const loading = ref(false)
const total = ref(0)

const pagination = computed(() => ({
  current: query.page,
  pageSize: query.pageSize,
  total: total.value,
  showSizeChanger: true,
  showTotal: (t) => `共 ${t} 条`,
}))

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 50 },
  { title: '网站名称', dataIndex: 'source_id', key: 'source_name', width: 160 },
  { title: '栏目名称', dataIndex: 'source_id', key: 'column_name', width: 120 },
  { title: '生成方式', dataIndex: 'generated_by', key: 'generated_by', width: 100 },
  { title: '版本', dataIndex: 'rule_version', key: 'rule_version', width: 60 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'action', width: 140, fixed: 'right' },
]

const { sourceInfoMap, loadForTable } = useSourceInfo()

function genModeColor(mode) {
  const map = { llm: 'blue', manual: 'green', platform: 'cyan' }
  return map[mode] || 'default'
}

function genModeLabel(mode) {
  const map = { llm: 'LLM生成', manual: '手动编写', platform: '平台适配' }
  return map[mode] || mode
}

async function fetchList() {
  loading.value = true
  try {
    const params = {}
    if (query.templateType) params.templateType = query.templateType
    if (query.keyword) params.keyword = query.keyword
    params.page = query.page
    params.pageSize = query.pageSize
    const res = await ruleApi.list(params)
    const page = res || {}
    tableData.value = page.records || (Array.isArray(page) ? page : [])
    // 加载当前页规则关联的采集源名称
    loadForTable(tableData.value)
    total.value = page.total || 0
  } catch {
    // error handled globally
  } finally {
    loading.value = false
  }
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

function onDelete(record) {
  Modal.confirm({
    title: '删除规则',
    content: `确认删除该规则？此操作不可撤销。`,
    okType: 'danger',
    onOk: async () => {
      try {
        await ruleApi.delete(record.id)
        message.success('删除成功')
        fetchList()
      } catch {
        // handled globally
      }
    },
  })
}

onMounted(() => {
  fetchList()
})
</script>
