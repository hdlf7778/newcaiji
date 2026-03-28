<template>
  <div class="review-workbench">
    <!-- Header -->
    <div class="review-header-bar">
      <h2 class="page-title">审核工作台</h2>
      <div class="header-stats">
        <span>待审核: <strong class="text-warning">{{ stats.pending }}</strong></span>
        <a-divider type="vertical" />
        <span>今日已审: <strong>{{ stats.todayReviewed }}</strong></span>
        <a-divider type="vertical" />
        <span>审批率: <strong>{{ stats.approvalRate }}%</strong></span>
        <a-divider type="vertical" />
        <span class="kbd-hint">
          快捷键:
          <kbd>Y</kbd>=通过
          <kbd>N</kbd>=跳过
          <kbd>R</kbd>=拒绝
          <kbd>E</kbd>=编辑规则
        </span>
      </div>
    </div>

    <!-- Batch approve button for perfect scores -->
    <div v-if="perfectScoreCount > 0" style="margin-bottom: 16px;">
      <a-button type="primary" @click="batchApprovePerfect">
        评分5/5一键全部通过 ({{ perfectScoreCount }} 个)
      </a-button>
    </div>

    <!-- Loading state -->
    <div v-if="loading" style="text-align: center; padding: 60px;">
      <a-spin size="large" />
    </div>

    <!-- Empty state -->
    <a-empty v-else-if="reviewList.length === 0" description="暂无待审核的采集源" />

    <!-- Review cards -->
    <div v-else>
      <div
        v-for="(item, index) in reviewList"
        :key="item.id"
        :ref="el => { if (el) cardRefs[index] = el }"
        class="review-card"
        :class="{ 'review-card-active': index === currentIndex }"
      >
        <!-- Card header -->
        <div class="card-header-row">
          <div>
            <div class="source-title">
              #{{ item.id }} {{ item.name }} — {{ item.column_name }}
            </div>
            <div class="source-meta">
              URL: {{ item.url }}
              &nbsp;|&nbsp; 模板: {{ item.template_code }}
              &nbsp;|&nbsp; 地区: {{ item.region }}
              &nbsp;|&nbsp; 优先级: {{ item.priority }}
            </div>
          </div>
          <div>
            <a-tag :color="getScoreColor(item.trial_score, item.trial_total)">
              试采 {{ item.trial_score }}/{{ item.trial_total }}
              {{ item.trial_score === item.trial_total ? '✅' : '⚠️' }}
            </a-tag>
          </div>
        </div>

        <!-- Trial articles -->
        <a-row :gutter="10" style="margin-bottom: 12px;">
          <a-col :span="8" v-for="(article, ai) in item.trial_articles" :key="ai">
            <div class="trial-card" :class="{ 'trial-card-warning': hasFailedCheck(article) }">
              <div class="trial-title">📄 {{ article.title }}</div>
              <div class="trial-meta">{{ article.date }} | 正文{{ article.word_count }}字</div>
              <div class="trial-checks">
                <span v-for="(passed, checkName) in article.checks" :key="checkName">
                  {{ passed ? '✅' : '❌' }} {{ checkName }}
                </span>
              </div>
            </div>
          </a-col>
        </a-row>

        <!-- Warning bar -->
        <a-alert
          v-if="getFailedChecks(item).length > 0"
          type="warning"
          :message="`⚠️ ${getFailedChecks(item).join(', ')} 未通过`"
          style="margin-bottom: 10px;"
          show-icon
        />

        <!-- Action buttons -->
        <div class="card-actions">
          <a-button type="primary" style="background: #52c41a; border-color: #52c41a;" @click="approveSource(item, index)">
            ✅ 通过
          </a-button>
          <a-button @click="retryWithEdit(item)">
            ✏️ 修改规则后重试
          </a-button>
          <a-button @click="skipSource(index)">
            ⏭️ 跳过
          </a-button>
          <a-button danger @click="rejectSource(item, index)">
            ❌ 拒绝
          </a-button>
          <a-button style="margin-left: auto;" :href="item.url" target="_blank">
            🔗 打开原网站
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { sourceApi } from '../../api/source.js'

const router = useRouter()

const loading = ref(false)
const reviewList = ref([])
const currentIndex = ref(0)
const cardRefs = ref([])

const stats = computed(() => {
  const pending = reviewList.value.length
  return {
    pending,
    todayReviewed: 0,
    approvalRate: 0,
  }
})

const perfectScoreCount = computed(() => {
  return reviewList.value.filter(item => item.trial_score === item.trial_total).length
})

function getScoreColor(score, total) {
  if (score === total) return 'green'
  if (score >= total * 0.8) return 'orange'
  return 'red'
}

function hasFailedCheck(article) {
  if (!article.checks) return false
  return Object.values(article.checks).some(v => !v)
}

function getFailedChecks(item) {
  const failed = []
  if (!item.trial_articles) return failed
  for (const article of item.trial_articles) {
    if (!article.checks) continue
    for (const [checkName, passed] of Object.entries(article.checks)) {
      if (!passed && !failed.includes(checkName)) {
        failed.push(checkName)
      }
    }
  }
  return failed
}

async function fetchReviewList() {
  loading.value = true
  try {
    const res = await sourceApi.reviewList()
    const page = res || {}
    reviewList.value = page.records || (Array.isArray(page) ? page : [])
  } catch (e) {
    message.error('加载审核列表失败')
  } finally {
    loading.value = false
  }
}

async function approveSource(item, index) {
  try {
    await sourceApi.approve(item.id, 'admin')
    message.success(`#${item.id} 已通过`)
    reviewList.value.splice(index, 1)
    if (currentIndex.value >= reviewList.value.length) {
      currentIndex.value = Math.max(0, reviewList.value.length - 1)
    }
  } catch (e) {
    message.error('操作失败')
  }
}

async function rejectSource(item, index) {
  try {
    await sourceApi.reject(item.id)
    message.warning(`#${item.id} 已拒绝`)
    reviewList.value.splice(index, 1)
    if (currentIndex.value >= reviewList.value.length) {
      currentIndex.value = Math.max(0, reviewList.value.length - 1)
    }
  } catch (e) {
    message.error('操作失败')
  }
}

function skipSource(index) {
  currentIndex.value = (index + 1) % reviewList.value.length
  const el = cardRefs.value[currentIndex.value]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function retryWithEdit(item) {
  router.push({ name: 'SourceDetail', params: { id: item.id } })
}

async function batchApprovePerfect() {
  const perfectIds = reviewList.value
    .filter(item => item.trial_score === item.trial_total)
    .map(item => item.id)
  if (perfectIds.length === 0) return
  try {
    await sourceApi.batchApprove(perfectIds, 'admin')
    message.success(`${perfectIds.length} 个采集源已批量通过`)
    reviewList.value = reviewList.value.filter(item => item.trial_score !== item.trial_total)
  } catch (e) {
    message.error('批量操作失败')
  }
}

function handleKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  const item = reviewList.value[currentIndex.value]
  if (!item) return
  switch (e.key.toLowerCase()) {
    case 'y':
      approveSource(item, currentIndex.value)
      break
    case 'n':
      skipSource(currentIndex.value)
      break
    case 'r':
      rejectSource(item, currentIndex.value)
      break
    case 'e':
      retryWithEdit(item)
      break
  }
}

onMounted(() => {
  fetchReviewList()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.review-workbench {
  padding: 0;
}

.review-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.header-stats {
  font-size: 13px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 4px;
}

.text-warning {
  color: #fa8c16;
}

.kbd-hint kbd {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  border: 1px solid #ddd;
  margin: 0 2px;
}

.review-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  transition: box-shadow 0.2s;
}

.review-card-active {
  box-shadow: 0 0 0 2px #1677ff40;
  border-color: #1677ff;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.source-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.source-meta {
  font-size: 12px;
  color: #888;
}

.trial-card {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 10px;
  background: #fafafa;
}

.trial-card-warning {
  border-color: #fa8c16;
}

.trial-title {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trial-meta {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.trial-checks {
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
</style>
