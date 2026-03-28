<!--
  监控仪表盘（Dashboard）

  功能：
    - 顶部统计卡片：点击可跳转到对应列表页（带筛选参数）
    - 告警区域：展示访问异常、规则失效、长期静默的采集源
    - 图表区域：模板健康度横向柱状图 + 今日采集趋势柱状图
    - 每 60 秒自动刷新仪表盘数据
-->
<template>
  <div class="dashboard">
    <!-- Stat cards row -->
    <div class="stat-row">
      <div class="stat-card clickable" @click="$router.push('/sources?status=ACTIVE')">
        <div class="stat-label">活跃采集源</div>
        <div class="stat-value blue">{{ dash.active_sources ?? '--' }}</div>
      </div>
      <div class="stat-card clickable" @click="$router.push('/sources?status=PENDING_DETECT')">
        <div class="stat-label">待检测</div>
        <div class="stat-value">{{ dash.pending_detect ?? '--' }}</div>
      </div>
      <div class="stat-card clickable" @click="$router.push('/review')">
        <div class="stat-label">待审核</div>
        <div class="stat-value orange">{{ dash.pending_review ?? '--' }}</div>
      </div>
      <div class="stat-card clickable" @click="$router.push('/sources?status=ERROR')">
        <div class="stat-label">异常</div>
        <div class="stat-value red">{{ dash.error_count ?? '--' }}</div>
      </div>
      <div class="stat-card clickable" @click="$router.push('/articles')">
        <div class="stat-label">今日新增文章</div>
        <div class="stat-value green">{{ dash.today_articles ?? '--' }}</div>
      </div>
      <div class="stat-card clickable" @click="$router.push('/tasks')">
        <div class="stat-label">当前成功率</div>
        <div class="stat-value green">{{ dash.success_rate != null ? dash.success_rate + '%' : '--' }}</div>
      </div>
      <div class="stat-card clickable" @click="$router.push('/tasks?status=pending')">
        <div class="stat-label">队列积压</div>
        <div class="stat-value">{{ dash.queue_backlog ?? '--' }}</div>
      </div>
    </div>

    <!-- Alert section -->
    <a-card style="margin-bottom: 16px;">
      <template #title>⚠️ 需要关注</template>

      <!-- 访问异常 -->
      <div class="alert-box alert-red">
        <div class="alert-content">
          <div class="alert-title">🔴 访问异常（今日新增 {{ dash.error_sources?.length ?? 0 }} 个）</div>
          <div class="alert-desc">
            <span v-if="dash.error_sources && dash.error_sources.length > 0">
              <span v-for="(s, i) in dash.error_sources.slice(0, 3)" :key="s.id">
                #{{ s.id }} {{ s.name }} — {{ s.error_msg }}
                <span v-if="i < Math.min(dash.error_sources.length, 3) - 1"> &nbsp;|&nbsp; </span>
              </span>
            </span>
            <span v-else>暂无访问异常</span>
          </div>
        </div>
        <div class="alert-action">
          <a-button size="small" @click="$router.push('/sources')">查看全部 →</a-button>
        </div>
      </div>

      <!-- 疑似规则失效 -->
      <div class="alert-box alert-orange">
        <div class="alert-content">
          <div class="alert-title">🟡 疑似规则失效（今日新增 {{ dash.detect_failed?.length ?? 0 }} 个）</div>
          <div class="alert-desc">
            <span v-if="dash.detect_failed && dash.detect_failed.length > 0">
              <span v-for="(s, i) in dash.detect_failed.slice(0, 3)" :key="s.id">
                #{{ s.id }} {{ s.name }} — {{ s.error_msg }}
                <span v-if="i < Math.min(dash.detect_failed.length, 3) - 1"> &nbsp;|&nbsp; </span>
              </span>
            </span>
            <span v-else>暂无规则失效</span>
          </div>
        </div>
        <div class="alert-action">
          <a-button size="small" @click="$router.push('/sources')">查看全部 →</a-button>
        </div>
      </div>

      <!-- 长期静默 -->
      <div class="alert-box alert-green">
        <div class="alert-content">
          <div class="alert-title">🟢 长期静默（超30天无新内容，共 {{ dash.silent_count ?? 0 }} 个）</div>
          <div class="alert-desc">这些站点可能已停止更新，建议定期复核</div>
        </div>
        <div class="alert-action">
          <a-button size="small">查看全部 →</a-button>
        </div>
      </div>
    </a-card>

    <!-- Charts row -->
    <a-row :gutter="16">
      <!-- Template health bar chart -->
      <a-col :span="12">
        <a-card title="模板健康度">
          <v-chart :option="templateHealthOption" autoresize style="height: 280px;" />
        </a-card>
      </a-col>

      <!-- Today's trend bar chart -->
      <a-col :span="12">
        <a-card title="今日采集趋势">
          <v-chart :option="trendOption" autoresize style="height: 280px;" />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { monitorApi } from '../api/monitor.js'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const dash = ref({})  // 仪表盘全部数据
let timer = null       // 自动刷新定时器

/** 拉取仪表盘数据，静默失败（不打断用户） */
async function fetchDashboard() {
  try {
    const res = await monitorApi.dashboard()
    dash.value = res || {}
  } catch (e) {
    // silently fail on refresh
  }
}

// 模板健康度横向柱状图配置（API 无数据时使用硬编码 fallback）
const templateHealthOption = computed(() => {
  const templates = dash.value.template_health || [
    { name: 'A 静态列表', rate: 97.1 },
    { name: 'B iframe', rate: 94.3 },
    { name: 'C API接口', rate: 98.5 },
    { name: 'D 微信', rate: 89.2 },
    { name: 'G SPA渲染', rate: 93.8 },
    { name: 'I 政务云', rate: 99.1 },
  ]

  const names = templates.map(t => t.name)
  const rates = templates.map(t => t.rate)
  const colors = rates.map(r => (r >= 95 ? '#52c41a' : r >= 90 ? '#fa8c16' : '#ff4d4f'))

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', top: '3%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'value',
      min: 80,
      max: 100,
      axisLabel: { formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: names,
    },
    series: [
      {
        type: 'bar',
        data: rates.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
        label: { show: true, position: 'right', formatter: '{c}%' },
      },
    ],
  }
})

// 今日采集趋势柱状图配置（按小时维度）
const trendOption = computed(() => {
  const trend = dash.value.today_trend || [
    { hour: '08:00', count: 3247 },
    { hour: '10:00', count: 2891 },
    { hour: '12:00', count: 1523 },
    { hour: '14:00', count: 2103 },
    { hour: '16:00', count: 2567 },
    { hour: '18:00', count: 0 },
    { hour: '20:00', count: 0 },
  ]

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', top: '8%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: trend.map(t => t.hour),
    },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: trend.map(t => t.count),
        itemStyle: { color: '#1677ff' },
        label: { show: true, position: 'top', formatter: params => params.value > 0 ? params.value : '' },
      },
    ],
  }
})

onMounted(() => {
  fetchDashboard()
  timer = setInterval(fetchDashboard, 60000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.stat-card.clickable {
  cursor: pointer;
  transition: all 0.2s;
}

.stat-card.clickable:hover {
  border-color: #1677ff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.15);
  transform: translateY(-2px);
}

.stat-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #333;
}

.stat-value.blue { color: #1677ff; }
.stat-value.orange { color: #fa8c16; }
.stat-value.red { color: #ff4d4f; }
.stat-value.green { color: #52c41a; }

.alert-box {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 10px;
  gap: 12px;
}

.alert-box:last-child {
  margin-bottom: 0;
}

.alert-red { background: #fff2f0; border: 1px solid #ffccc7; }
.alert-orange { background: #fffbe6; border: 1px solid #ffe58f; }
.alert-green { background: #f6ffed; border: 1px solid #b7eb8f; }

.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.alert-desc {
  font-size: 12px;
  color: #666;
}
</style>
