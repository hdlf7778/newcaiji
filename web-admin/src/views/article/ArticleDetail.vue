<template>
  <div>
    <!-- Header -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
      <a-button @click="$router.back()">← 返回</a-button>
      <h2 style="font-size:18px;font-weight:600;margin:0;">文章详情</h2>
    </div>

    <a-spin :spinning="loading">
      <template v-if="article">
        <!-- Meta info -->
        <a-card style="margin-bottom:16px;" title="基本信息">
          <a-descriptions :column="2" size="small">
            <a-descriptions-item label="标题" :span="2">
              <span style="font-weight:600;font-size:15px;">{{ article.title }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="发布时间（原始）">
              {{ article.publishTimeRaw || '—' }}
            </a-descriptions-item>
            <a-descriptions-item label="发布时间（标准化）">
              {{ article.publishTime || '—' }}
            </a-descriptions-item>
            <a-descriptions-item label="来源">
              {{ article.sourceName || '—' }}
            </a-descriptions-item>
            <a-descriptions-item label="所属网站 / 栏目">
              {{ article.siteName || article.sourceName || '—' }}
              <template v-if="article.columnName"> / {{ article.columnName }}</template>
            </a-descriptions-item>
            <a-descriptions-item label="原文URL" :span="2">
              <a :href="safeUrl(article.url)" target="_blank" rel="noopener noreferrer" style="color:#1677ff;word-break:break-all;">
                {{ article.url }}
                <LinkOutlined style="margin-left:4px;" />
              </a>
            </a-descriptions-item>
            <a-descriptions-item label="采集时间">
              {{ article.crawledAt || '—' }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- Content -->
        <a-card style="margin-bottom:16px;" title="正文内容">
          <div
            v-if="sanitizedHtml"
            class="article-content"
            v-html="sanitizedHtml"
          />
          <div v-else-if="article.content" class="article-content" style="white-space:pre-wrap;">
            {{ article.content }}
          </div>
          <div v-else style="color:#8c8c8c;text-align:center;padding:40px 0;">
            暂无正文内容
          </div>
        </a-card>

        <!-- Attachments -->
        <a-card v-if="attachments.length > 0" title="附件">
          <a-list
            :data-source="attachments"
            size="small"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-space>
                  <a-tag :color="fileTypeColor(item.fileType)">
                    {{ item.fileType || 'FILE' }}
                  </a-tag>
                  <a :href="safeUrl(item.fileUrl)" target="_blank" rel="noopener noreferrer" style="color:#1677ff;">
                    {{ item.fileName || item.fileUrl }}
                  </a>
                  <DownloadOutlined />
                </a-space>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </template>

      <a-empty v-else-if="!loading" description="文章不存在或已被删除" />
    </a-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { LinkOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import { articleApi } from '../../api/article.js'
import DOMPurify from 'dompurify'
import { safeUrl } from '../../utils/safeUrl.js'

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.hasAttribute('href')) {
    const href = node.getAttribute('href') || ''
    if (/^(javascript|data):/i.test(href.trim())) {
      node.removeAttribute('href')
    }
  }
  if (node.hasAttribute('target')) {
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

const route = useRoute()
const articleId = route.params.id

const article = ref(null)
const loading = ref(false)

const sanitizedHtml = computed(() => {
  const raw = article.value?.contentHtml || article.value?.content_html || ''
  return DOMPurify.sanitize(raw, { ALLOWED_TAGS: ['p', 'br', 'b', 'i', 'strong', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'a', 'table', 'tr', 'td', 'th', 'thead', 'tbody', 'span', 'div', 'img', 'blockquote', 'pre', 'code'], ALLOWED_ATTR: ['href', 'src', 'alt', 'class', 'target'] })
})

const attachments = computed(() => {
  if (!article.value) return []
  const raw = article.value.attachments
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  try {
    return JSON.parse(raw)
  } catch {
    return []
  }
})

function fileTypeColor(type) {
  if (!type) return 'default'
  const t = type.toLowerCase()
  if (t.includes('pdf')) return 'red'
  if (t.includes('doc') || t.includes('word')) return 'blue'
  if (t.includes('xls') || t.includes('excel')) return 'green'
  if (t.includes('zip') || t.includes('rar')) return 'orange'
  if (t.includes('jpg') || t.includes('png') || t.includes('image')) return 'purple'
  return 'default'
}

async function fetchDetail() {
  loading.value = true
  try {
    const res = await articleApi.detail(articleId)
    article.value = res || {}
  } catch {
    message.error('加载文章失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDetail()
})
</script>

<style scoped>
.article-content {
  font-size: 15px;
  line-height: 1.9;
  color: #262626;
}
.article-content :deep(p) {
  margin-bottom: 12px;
}
.article-content :deep(h1),
.article-content :deep(h2),
.article-content :deep(h3) {
  font-weight: 600;
  margin: 16px 0 8px;
}
.article-content :deep(img) {
  max-width: 100%;
  height: auto;
}
.article-content :deep(a) {
  color: #1677ff;
}
.article-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 12px;
}
.article-content :deep(td),
.article-content :deep(th) {
  border: 1px solid #d9d9d9;
  padding: 6px 10px;
}
</style>
