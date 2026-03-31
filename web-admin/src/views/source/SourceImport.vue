<template>
  <div>
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h2 style="font-size:18px;font-weight:600;margin:0;">批量导入采集源</h2>
      <a-space>
        <router-link to="/sources">
          <a-button>返回列表</a-button>
        </router-link>
        <a-button type="link" @click="downloadTemplate">
          <template #icon><DownloadOutlined /></template>
          下载CSV模板
        </a-button>
      </a-space>
    </div>

    <!-- Upload area -->
    <a-card title="上传文件" style="margin-bottom:16px;">
      <a-upload-dragger
        v-model:file-list="fileList"
        name="file"
        :before-upload="beforeUpload"
        :multiple="false"
        accept=".csv,.xlsx,.xls"
        :show-upload-list="false"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p class="ant-upload-hint">支持 CSV、Excel (.xlsx / .xls) 格式，文件大小不超过 10MB</p>
      </a-upload-dragger>

      <div v-if="fileName" style="margin-top:12px;display:flex;align-items:center;gap:8px;color:#52c41a;">
        <FileExcelOutlined />
        <span>{{ fileName }}</span>
        <a-button type="text" size="small" danger @click="clearFile">
          <template #icon><CloseCircleOutlined /></template>
        </a-button>
      </div>
    </a-card>

    <!-- Preview table -->
    <a-card v-if="previewData.length > 0" title="数据预览（前10行）" style="margin-bottom:16px;">
      <div style="margin-bottom:8px;font-size:13px;color:#8c8c8c;">
        共解析 {{ totalRows }} 行数据，以下展示前10行预览
      </div>
      <a-table
        :columns="previewColumns"
        :data-source="previewData"
        :pagination="false"
        size="small"
        row-key="_idx"
        :scroll="{ x: 900 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'priority'">
            {{ record.priority || '6' }}
          </template>
          <template v-if="column.key === 'templateType'">
            <a-tag v-if="record.templateType" :color="templateColor(record.templateType)">
              {{ record.templateType }}
            </a-tag>
            <span v-else style="color:#8c8c8c;">自动</span>
          </template>
        </template>
      </a-table>

      <div style="margin-top:16px;">
        <a-button
          type="primary"
          size="large"
          :loading="importing"
          :disabled="!previewData.length && !rawFile"
          @click="startImport"
        >
          <template #icon><UploadOutlined /></template>
          开始导入（{{ totalRows || '?' }} 条）
        </a-button>
      </div>

      <!-- Import progress -->
      <div v-if="importing || importProgressStatus === 'exception' || importProgressStatus === 'success'" style="margin-top:16px;">
        <a-progress
          :percent="importProgress"
          :status="importProgressStatus"
          :stroke-color="importProgress < 100 ? undefined : '#52c41a'"
          :format="() => importProgress + '%'"
        />
        <div style="margin-top:8px;display:flex;align-items:center;justify-content:space-between;">
          <span style="font-size:13px;color:#8c8c8c;">{{ importProgressText }}</span>
          <a-button
            v-if="importing"
            type="text"
            danger
            size="small"
            @click="cancelImport"
          >
            终止导入
          </a-button>
        </div>
        <div v-if="importedCount + duplicateCount + invalidCount > 0" style="margin-top:6px;display:flex;gap:16px;font-size:13px;">
          <span style="color:#52c41a;">成功 {{ importedCount }}</span>
          <span style="color:#fa8c16;">重复 {{ duplicateCount }}</span>
          <span style="color:#ff4d4f;">失败 {{ invalidCount }}</span>
          <span style="color:#8c8c8c;">共 {{ totalRows }} 条</span>
        </div>
      </div>
    </a-card>

    <!-- Import result modal -->
    <a-modal
      v-model:open="resultVisible"
      title="导入结果"
      :footer="null"
      width="600px"
    >
      <div v-if="importResult">
        <a-row :gutter="16" style="margin-bottom:20px;">
          <a-col :span="6">
            <a-statistic title="总计" :value="importResult.total" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="导入成功" :value="importResult.imported" value-style="color:#52c41a" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="重复跳过" :value="importResult.duplicates" value-style="color:#fa8c16" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="无效数据" :value="importResult.invalid" value-style="color:#ff4d4f" />
          </a-col>
        </a-row>

        <div v-if="importResult.errors && importResult.errors.length">
          <div style="font-weight:600;margin-bottom:8px;">错误详情</div>
          <a-table
            :columns="errorColumns"
            :data-source="importResult.errors"
            :pagination="false"
            size="small"
            row-key="row"
          />
        </div>

        <div style="margin-top:16px;text-align:right;">
          <a-space>
            <a-button @click="resultVisible = false">关闭</a-button>
            <router-link to="/sources">
              <a-button type="primary">查看采集源列表</a-button>
            </router-link>
          </a-space>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  InboxOutlined,
  DownloadOutlined,
  UploadOutlined,
  FileExcelOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons-vue'
import { sourceApi } from '../../api/source.js'
import request from '../../api/request.js'

const fileList = ref([])
const fileName = ref('')
const totalRows = ref(0)
const previewData = ref([])
const allParsedRows = ref([])  // CSV: all parsed rows for row-by-row import
const importing = ref(false)
const importProgress = ref(0)
const importProgressStatus = ref('active')
const importProgressText = ref('')
const importedCount = ref(0)
const duplicateCount = ref(0)
const invalidCount = ref(0)
const resultVisible = ref(false)
const importResult = ref(null)
let progressTimer = null
let abortController = null
let cancelled = false

// Store raw file for actual upload
let rawFile = null

const previewColumns = [
  { title: 'URL', dataIndex: 'url', key: 'url', width: 220, ellipsis: true },
  { title: '网站名称', dataIndex: 'name', key: 'name', width: 140 },
  { title: '栏目名称', dataIndex: 'columnName', key: 'columnName', width: 120 },
  { title: '地区', dataIndex: 'region', key: 'region', width: 100 },
  { title: '分类', dataIndex: 'category', key: 'category', width: 90 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 75 },
  { title: '模板', dataIndex: 'templateType', key: 'templateType', width: 90 },
  { title: '平台', dataIndex: 'platform', key: 'platform', width: 100 },
]

const errorColumns = [
  { title: '行号', dataIndex: 'row', key: 'row', width: 70 },
  { title: '错误原因', dataIndex: 'message', key: 'message' },
]

function templateColor(type) {
  const map = { A: 'purple', B: 'orange', C: 'blue', D: 'purple', G: 'red', H: 'green', I: 'cyan', J: 'default' }
  return map[type] || 'default'
}

function beforeUpload(file) {
  const isValidType = [
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ].includes(file.type) || file.name.match(/\.(csv|xlsx|xls)$/i)

  if (!isValidType) {
    message.error('只支持 CSV、Excel 格式文件')
    return false
  }

  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    message.error('文件大小不能超过 10MB')
    return false
  }

  rawFile = file
  fileName.value = file.name
  parseFile(file)
  return false // prevent auto upload
}

function parseFile(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target.result
    if (file.name.endsWith('.csv')) {
      parseCsv(content)
    } else {
      // For Excel, show a placeholder message since we can't parse xlsx without a library
      message.info('Excel 文件将在服务器端解析，预览功能仅支持 CSV')
      // Create minimal preview from file name
      previewData.value = []
      totalRows.value = 0
    }
  }
  if (file.name.endsWith('.csv')) {
    reader.readAsText(file, 'UTF-8')
  } else {
    reader.readAsArrayBuffer(file)
  }
}

function parseCsv(content) {
  const lines = content.split('\n').filter((l) => l.trim())
  if (lines.length < 2) {
    message.warning('文件内容为空或只有表头')
    return
  }

  const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''))
  const headerMap = buildHeaderMap(headers)

  const rows = []
  for (let i = 1; i < lines.length; i++) {
    const cols = parseCsvLine(lines[i])
    if (!cols.some((c) => c.trim())) continue
    const row = { _idx: i }
    for (const [field, idx] of Object.entries(headerMap)) {
      row[field] = idx >= 0 ? (cols[idx] || '').trim() : ''
    }
    rows.push(row)
  }

  totalRows.value = rows.length
  allParsedRows.value = rows
  previewData.value = rows.slice(0, 10)
}

function buildHeaderMap(headers) {
  const fieldAliases = {
    url: ['url', 'URL', '链接', '网址'],
    name: ['name', 'Name', '网站名称', '名称'],
    columnName: ['columnName', 'column_name', '栏目名称', '栏目'],
    region: ['region', 'Region', '地区'],
    category: ['category', 'Category', '分类'],
    priority: ['priority', 'Priority', '优先级'],
    templateType: ['templateType', 'template_type', 'template', '模板', '模板类型'],
    platform: ['platform', 'Platform', '平台'],
  }

  const map = {}
  for (const [field, aliases] of Object.entries(fieldAliases)) {
    map[field] = -1
    for (const alias of aliases) {
      const idx = headers.indexOf(alias)
      if (idx >= 0) {
        map[field] = idx
        break
      }
    }
  }
  return map
}

function parseCsvLine(line) {
  const result = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    if (char === '"') {
      inQuotes = !inQuotes
    } else if (char === ',' && !inQuotes) {
      result.push(current)
      current = ''
    } else {
      current += char
    }
  }
  result.push(current)
  return result
}

function clearFile() {
  rawFile = null
  fileName.value = ''
  previewData.value = []
  allParsedRows.value = []
  totalRows.value = 0
  fileList.value = []
}

function resetProgress() {
  importProgress.value = 0
  importProgressStatus.value = 'active'
  importProgressText.value = ''
  importedCount.value = 0
  duplicateCount.value = 0
  invalidCount.value = 0
  cancelled = false
}

function startProcessingProgress() {
  let current = importProgress.value
  progressTimer = setInterval(() => {
    if (current < 95) {
      current += Math.random() * 3 + 0.5
      if (current > 95) current = 95
      importProgress.value = Math.round(current)
    }
  }, 500)
}

function stopProcessingProgress() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

function cancelImport() {
  cancelled = true
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  stopProcessingProgress()
  importing.value = false
  importProgressStatus.value = 'exception'
  const done = importedCount.value + duplicateCount.value + invalidCount.value
  importProgressText.value = `\u5DF2\u7EC8\u6B62\u5BFC\u5165\uFF08\u5DF2\u5904\u7406 ${done} / ${totalRows.value} \u6761\uFF09`
  message.warning('\u5BFC\u5165\u5DF2\u7EC8\u6B62')
}

/** CSV: batch import with real progress (200 items per batch) */
async function importInBatches() {
  const rows = allParsedRows.value
  const total = rows.length
  const BATCH_SIZE = 200
  const allErrors = []
  let processed = 0

  for (let start = 0; start < total; start += BATCH_SIZE) {
    if (cancelled) return

    const chunk = rows.slice(start, start + BATCH_SIZE)
    const items = chunk.map((row) => ({
      url: row.url || '',
      name: row.name || row.url || '',
      column_name: row.columnName || '',
      region: row.region || '',
      priority: parseInt(row.priority) || 6,
      template: row.templateType || null,
      platform: row.platform || '',
    }))

    try {
      const res = await sourceApi.batchCreate(items)
      importedCount.value += res?.imported || 0
      duplicateCount.value += res?.duplicates || 0
      invalidCount.value += res?.invalid || 0
      if (res?.errors?.length) {
        for (const err of res.errors) {
          allErrors.push({ row: start + err.row + 1, message: err.reason || err.message })
        }
      }
    } catch (e) {
      if (cancelled || e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return
      invalidCount.value += chunk.length
      allErrors.push({ row: start + 2, message: e?.message || '\u6279\u91CF\u521B\u5EFA\u5931\u8D25' })
    }

    processed = Math.min(start + BATCH_SIZE, total)
    importProgress.value = Math.round((processed / total) * 100)
    importProgressText.value = `\u6B63\u5728\u5BFC\u5165\u2026 ${processed} / ${total}`
  }

  return {
    total,
    imported: importedCount.value,
    duplicates: duplicateCount.value,
    invalid: invalidCount.value,
    errors: allErrors.slice(0, 50),
  }
}

/** Excel: file upload with simulated progress */
async function importViaFileUpload() {
  abortController = new AbortController()
  let uploadDone = false
  importProgressText.value = '\u6B63\u5728\u4E0A\u4F20\u6587\u4EF6\u2026'

  const formData = new FormData()
  formData.append('file', rawFile)

  const res = await request.post('/api/sources/import', formData, {
    timeout: 120000,
    signal: abortController.signal,
    onUploadProgress: (e) => {
      if (e.total) {
        const pct = Math.round((e.loaded / e.total) * 50)
        importProgress.value = pct
        if (e.loaded < e.total) {
          importProgressText.value = `\u6B63\u5728\u4E0A\u4F20\u6587\u4EF6\u2026 ${Math.round(e.loaded / 1024)}KB / ${Math.round(e.total / 1024)}KB`
        } else if (!uploadDone) {
          uploadDone = true
          importProgress.value = 50
          importProgressText.value = `\u670D\u52A1\u7AEF\u6B63\u5728\u89E3\u6790\u5E76\u5BFC\u5165\u2026`
          startProcessingProgress()
        }
      }
    },
  })

  stopProcessingProgress()
  importedCount.value = res?.imported || 0
  duplicateCount.value = res?.duplicates || 0
  invalidCount.value = res?.invalid || 0
  return res
}

async function startImport() {
  if (!rawFile) {
    message.warning('\u8BF7\u5148\u9009\u62E9\u6587\u4EF6')
    return
  }

  importing.value = true
  resetProgress()

  const isCsv = rawFile.name.toLowerCase().endsWith('.csv') && allParsedRows.value.length > 0

  try {
    let res
    if (isCsv) {
      res = await importInBatches()
    } else {
      res = await importViaFileUpload()
    }

    if (cancelled) return

    importProgress.value = 100
    importProgressStatus.value = 'success'
    importProgressText.value = `\u5BFC\u5165\u5B8C\u6210\uFF1A\u6210\u529F ${importedCount.value}\u3001\u91CD\u590D ${duplicateCount.value}\u3001\u5931\u8D25 ${invalidCount.value}`

    importResult.value = res || {}
    resultVisible.value = true
  } catch (e) {
    stopProcessingProgress()
    if (cancelled || e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return
    importProgressStatus.value = 'exception'
    importProgressText.value = '\u5BFC\u5165\u5931\u8D25'
  } finally {
    importing.value = false
    abortController = null
  }
}

function downloadTemplate() {
  const headers = ['url', 'name', 'columnName', 'region', 'category', 'priority', 'templateType', 'platform']
  const example = [
    'https://example.gov.cn/col/index.html',
    '示例政府网站',
    '招考录用',
    '浙江-杭州',
    '事业单位',
    '6',
    'A',
    'JPAAS',
  ]
  const csvContent = [headers.join(','), example.join(',')].join('\n')
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = '采集源导入模板.csv'
  link.click()
  URL.revokeObjectURL(url)
}
</script>
