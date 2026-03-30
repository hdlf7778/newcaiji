<template>
  <div>
    <div style="margin-bottom:24px;">
      <h2 style="font-size:18px;font-weight:600;margin:0 0 20px;">新增采集源</h2>
      <a-steps :current="current" size="small" style="max-width:600px;">
        <a-step title="基本信息" />
        <a-step title="智能检测" />
        <a-step title="试采预览" />
        <a-step title="确认提交" />
      </a-steps>
    </div>

    <!-- Step 1: 基本信息 -->
    <a-card v-if="current === 0" title="填写采集源信息">
      <a-form
        ref="formRef"
        :model="formState"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 16 }"
        @finish="onStep1Finish"
      >
        <a-row :gutter="24">
          <a-col :span="12">
            <a-form-item label="网站名称" name="name" :rules="[{ required: true, message: '请输入网站名称' }]">
              <a-input v-model:value="formState.name" placeholder="如：海宁市人民政府" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="栏目名称" name="columnName">
              <a-input v-model:value="formState.columnName" placeholder="如：招考录用" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item
              label="网站链接"
              name="url"
              :rules="[{ required: true, message: '请输入URL' }, { type: 'url', message: '请输入有效URL' }]"
              :label-col="{ span: 3 }"
              :wrapper-col="{ span: 20 }"
            >
              <a-input
                v-model:value="formState.url"
                placeholder="https://..."
                style="font-family:'JetBrains Mono',monospace;font-size:13px;"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="地区" name="region">
              <a-input v-model:value="formState.region" placeholder="如：浙江-海宁" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="分类" name="category">
              <a-select v-model:value="formState.category" placeholder="请选择分类">
                <a-select-option value="事业单位">事业单位</a-select-option>
                <a-select-option value="公务员">公务员</a-select-option>
                <a-select-option value="卫健">卫健</a-select-option>
                <a-select-option value="教育">教育</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="优先级" name="priority">
              <a-select v-model:value="formState.priority">
                <a-select-option v-for="n in 10" :key="n" :value="n">{{ n }}</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="模板类型" name="templateType">
              <a-select v-model:value="formState.templateType">
                <a-select-option value="">自动检测</a-select-option>
                <a-select-option value="A">A 静态列表</a-select-option>
                <a-select-option value="B">B iframe</a-select-option>
                <a-select-option value="C">C API接口</a-select-option>
                <a-select-option value="D">D 微信</a-select-option>
                <a-select-option value="G">G SPA渲染</a-select-option>
                <a-select-option value="I">I 政务云</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 去重提示 -->
        <a-alert
          v-if="duplicateSource"
          type="warning"
          show-icon
          closable
          style="margin-top:12px;margin-bottom:12px;"
          @close="duplicateSource = null"
        >
          <template #message>该采集源已存在，无需重复添加</template>
          <template #description>
            <div style="margin-top:8px;">
              <a-descriptions :column="2" size="small" bordered>
                <a-descriptions-item label="ID">{{ duplicateSource.id }}</a-descriptions-item>
                <a-descriptions-item label="网站名称">{{ duplicateSource.name }}</a-descriptions-item>
                <a-descriptions-item label="栏目名称">{{ duplicateSource.column_name || '—' }}</a-descriptions-item>
                <a-descriptions-item label="状态">{{ duplicateSource.status }}</a-descriptions-item>
                <a-descriptions-item label="URL" :span="2">
                  <span style="font-size:12px;word-break:break-all;">{{ duplicateSource.url }}</span>
                </a-descriptions-item>
              </a-descriptions>
              <div style="margin-top:10px;">
                <router-link :to="`/sources/${duplicateSource.id}`">
                  <a-button type="primary" size="small">查看现有采集源</a-button>
                </router-link>
              </div>
            </div>
          </template>
        </a-alert>

        <div style="margin-top:8px;display:flex;gap:10px;">
          <a-button type="primary" html-type="submit" :loading="detecting">
            <template #icon><SearchOutlined /></template>
            开始智能检测
          </a-button>
          <router-link to="/sources">
            <a-button>取消</a-button>
          </router-link>
        </div>
      </a-form>
    </a-card>

    <!-- Step 2: 智能检测结果 -->
    <a-card v-if="current === 1" title="智能检测结果">
      <div v-if="detecting" style="text-align:center;padding:60px;">
        <a-spin size="large" />
        <div style="margin-top:16px;color:#8c8c8c;">正在检测中，请稍候...</div>
      </div>
      <div v-else-if="detectResult">
        <a-row :gutter="[16, 12]" style="margin-bottom:20px;">
          <a-col :span="12" v-for="item in detectItems" :key="item.key">
            <div style="display:flex;align-items:center;gap:8px;padding:10px;border:1px solid #f0f0f0;border-radius:6px;">
              <span style="font-size:16px;">{{ detectResult[item.key] ? '✅' : '❌' }}</span>
              <span style="font-size:13px;">{{ item.label }}：{{ detectResult[item.value] || '未检测到' }}</span>
            </div>
          </a-col>
        </a-row>
        <div style="display:flex;gap:10px;">
          <a-button type="primary" @click="current = 2">下一步：试采预览</a-button>
          <a-button @click="current = 0">返回修改</a-button>
        </div>
      </div>
      <a-empty v-else description="检测失败，请返回重试">
        <a-button @click="current = 0">返回</a-button>
      </a-empty>
    </a-card>

    <!-- Step 3: 试采预览 -->
    <a-card v-if="current === 2" title="试采预览">
      <div v-if="loadingTrial" style="text-align:center;padding:60px;">
        <a-spin size="large" />
        <div style="margin-top:16px;color:#8c8c8c;">正在试采，请稍候...</div>
      </div>
      <div v-else-if="trialResult">
        <div v-for="(article, idx) in (trialResult.articles || [])" :key="idx" class="trial-card">
          <div style="font-size:14px;font-weight:600;margin-bottom:6px;">
            📄 {{ article.title }}
          </div>
          <div style="font-size:12px;color:#8c8c8c;margin-bottom:6px;">
            发布时间：{{ article.publishTime }} | 来源：{{ article.source }}
          </div>
          <div style="font-size:13px;color:#595959;margin-bottom:8px;">
            {{ article.preview }}
          </div>
          <a-space>
            <span v-if="article.hasTitle" style="color:#52c41a;font-size:12px;">✅ 标题有效</span>
            <span v-else style="color:#ff4d4f;font-size:12px;">❌ 无标题</span>
            <span v-if="article.hasContent" style="color:#52c41a;font-size:12px;">✅ 正文{{ article.contentLength }}字</span>
            <span v-else style="color:#ff4d4f;font-size:12px;">❌ 无正文</span>
            <span v-if="article.hasTime" style="color:#52c41a;font-size:12px;">✅ 时间有效</span>
            <span v-else style="color:#ff4d4f;font-size:12px;">❌ 无时间</span>
          </a-space>
        </div>

        <!-- Score summary -->
        <div style="margin-top:16px;padding:14px;background:#f6ffed;border:1px solid #b7eb8f;border-radius:8px;display:flex;justify-content:space-between;align-items:center;">
          <strong>试采评分：{{ trialResult.score }}/{{ trialResult.maxScore }} ✅</strong>
          <span style="font-size:13px;color:#52c41a;">{{ trialResult.suggestion }}</span>
        </div>

        <div style="margin-top:16px;display:flex;gap:10px;">
          <a-button type="primary" @click="current = 3">下一步：确认提交</a-button>
          <a-button @click="current = 1">返回</a-button>
        </div>
      </div>
      <a-empty v-else description="试采失败，请返回重试">
        <a-button @click="current = 1">返回</a-button>
      </a-empty>
    </a-card>

    <!-- Step 4: 确认提交 -->
    <a-card v-if="current === 3" title="确认提交">
      <a-descriptions :column="2" bordered size="small" style="margin-bottom:20px;">
        <a-descriptions-item label="网站名称">{{ formState.name }}</a-descriptions-item>
        <a-descriptions-item label="栏目名称">{{ formState.columnName || '—' }}</a-descriptions-item>
        <a-descriptions-item label="URL" :span="2">
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;">{{ formState.url }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="地区">{{ formState.region || '—' }}</a-descriptions-item>
        <a-descriptions-item label="分类">{{ formState.category || '—' }}</a-descriptions-item>
        <a-descriptions-item label="优先级">{{ formState.priority }}</a-descriptions-item>
        <a-descriptions-item label="模板类型">
          {{ formState.templateType || '自动检测' }}
          <span v-if="detectResult?.templateType" style="margin-left:8px;color:#8c8c8c;">
            → 检测结果：{{ detectResult.templateType }}
          </span>
        </a-descriptions-item>
      </a-descriptions>

      <div v-if="trialResult" style="margin-bottom:20px;padding:12px;background:#f6ffed;border:1px solid #b7eb8f;border-radius:6px;">
        <strong>试采评分：{{ trialResult.score }}/{{ trialResult.maxScore }} ✅</strong>
        &nbsp; 建议：{{ trialResult.suggestion }}
      </div>

      <a-space>
        <a-button type="primary" :loading="submitting" @click="onConfirmSubmit">
          ✅ 确认通过，投入生产
        </a-button>
        <a-button @click="current = 0">
          ✏️ 修改规则
        </a-button>
        <router-link to="/sources">
          <a-button danger>❌ 放弃</a-button>
        </router-link>
      </a-space>
    </a-card>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import { sourceApi } from '../../api/source.js'
import request from '../../api/request.js'

const router = useRouter()

const current = ref(0)
const duplicateSource = ref(null)  // 去重检查发现的已有采集源
const detecting = ref(false)
const loadingTrial = ref(false)
const submitting = ref(false)

const formRef = ref(null)
const formState = reactive({
  name: '',
  columnName: '',
  url: '',
  region: '',
  category: '',
  priority: 6,
  templateType: '',
})

const detectResult = ref(null)
const trialResult = ref(null)
const createdId = ref(null)

const detectItems = [
  { key: 'templateDetected', label: '模板类型', value: 'templateType' },
  { key: 'platformDetected', label: '平台识别', value: 'platform' },
  { key: 'listRuleDetected', label: '列表规则', value: 'listRuleDesc' },
  { key: 'detailRuleDetected', label: '详情规则', value: 'detailRuleDesc' },
  { key: 'encodingDetected', label: '编码检测', value: 'encoding' },
]

async function onStep1Finish() {
  // 去重检查：name + columnName + url
  duplicateSource.value = null
  try {
    const dup = await request.get('/api/sources/check-duplicate', {
      params: { name: formState.name, columnName: formState.columnName || '', url: formState.url }
    })
    if (dup) {
      duplicateSource.value = dup
      return  // 不继续，页面会展示重复提示
    }
  } catch { /* 检查失败不阻塞流程 */ }

  detecting.value = true
  current.value = 1
  try {
    const createRes = await sourceApi.create({
      name: formState.name,
      columnName: formState.columnName,
      url: formState.url,
      region: formState.region,
      category: formState.category,
      priority: formState.priority,
      templateType: formState.templateType || null,
    })
    createdId.value = (createRes.data || createRes).id

    // Trigger detection
    const detectRes = await sourceApi.detect(createdId.value)
    detectResult.value = detectRes.data || detectRes

    // Load trial data
    loadingTrial.value = true
    const trialRes = await sourceApi.detail(createdId.value)
    const data = trialRes.data || trialRes
    trialResult.value = data.trialResult || null
  } catch {
    detectResult.value = null
  } finally {
    detecting.value = false
    loadingTrial.value = false
  }
}

// When advancing to step 3, load trial if not already loaded
watch(current, async (val) => {
  if (val === 2 && !trialResult.value && createdId.value && !loadingTrial.value) {
    loadingTrial.value = true
    try {
      const res = await sourceApi.detail(createdId.value)
      trialResult.value = res?.trialResult || res?.trial_result || null
    } catch {
      trialResult.value = null
    } finally {
      loadingTrial.value = false
    }
  }
})

async function onConfirmSubmit() {
  if (!createdId.value) return
  submitting.value = true
  try {
    await sourceApi.approve(createdId.value, 'admin')
    message.success('采集源已审批通过，即将投入生产')
    router.push('/sources')
  } catch {
    // handled globally
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.trial-card {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #fafafa;
}
</style>
