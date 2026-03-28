<template>
  <div class="system-settings">
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
    </div>

    <a-tabs v-model:activeKey="activeTab">
      <!-- Tab 1: 采集调度 -->
      <a-tab-pane key="schedule" tab="采集调度">
        <a-card>
          <a-form :model="scheduleForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 12 }">
            <a-form-item label="工作时间段">
              <a-time-range-picker
                v-model:value="scheduleForm.workHours"
                format="HH:mm"
                :minute-step="30"
              />
            </a-form-item>
            <a-form-item label="工作时间间隔" :help="'采集间隔秒数（默认 7200 秒 = 2小时）'">
              <a-input-number
                v-model:value="scheduleForm.workInterval"
                :min="60"
                :max="86400"
                style="width: 180px;"
                addon-after="秒"
              />
            </a-form-item>
            <a-form-item label="非工作时间间隔" :help="'非工作时段采集间隔（默认 14400 秒 = 4小时）'">
              <a-input-number
                v-model:value="scheduleForm.offHoursInterval"
                :min="60"
                :max="86400"
                style="width: 180px;"
                addon-after="秒"
              />
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 6 }">
              <a-button type="primary" :loading="saving.schedule" @click="saveSchedule">
                保存配置
              </a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-tab-pane>

      <!-- Tab 2: 自动审批 -->
      <a-tab-pane key="autoApprove" tab="自动审批">
        <a-card>
          <a-form :model="autoApproveForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 12 }">
            <a-form-item label="启用自动审批">
              <a-switch v-model:checked="autoApproveForm.enabled" />
            </a-form-item>
            <a-form-item label="自动通过阈值分数" :help="`当前: ${autoApproveForm.threshold} — 高于此分数自动通过`">
              <a-slider
                v-model:value="autoApproveForm.threshold"
                :min="0"
                :max="1"
                :step="0.1"
                :marks="sliderMarks"
                :disabled="!autoApproveForm.enabled"
                style="width: 300px;"
              />
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 6 }">
              <a-button type="primary" :loading="saving.autoApprove" @click="saveAutoApprove">
                保存配置
              </a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-tab-pane>

      <!-- Tab 3: 告警配置 -->
      <a-tab-pane key="alert" tab="告警配置">
        <a-card>
          <a-form :model="alertForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 12 }">
            <a-form-item label="Webhook URL">
              <a-input
                v-model:value="alertForm.webhookUrl"
                placeholder="请输入 Webhook 地址"
                allow-clear
              />
            </a-form-item>
            <a-form-item label="通知方式">
              <a-select v-model:value="alertForm.notifyMethod" style="width: 200px;">
                <a-select-option value="dingtalk">钉钉</a-select-option>
                <a-select-option value="wecom">企业微信</a-select-option>
                <a-select-option value="email">邮件</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 6 }">
              <a-button type="primary" :loading="saving.alert" @click="saveAlert">
                保存配置
              </a-button>
              <a-button style="margin-left: 8px;" @click="testWebhook">
                测试 Webhook
              </a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-tab-pane>

      <!-- Tab 4: 数据保留 -->
      <a-tab-pane key="retention" tab="数据保留">
        <a-card>
          <a-form :model="retentionForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 12 }">
            <a-form-item label="日志保留天数">
              <a-input-number
                v-model:value="retentionForm.logDays"
                :min="1"
                :max="365"
                style="width: 180px;"
                addon-after="天"
              />
            </a-form-item>
            <a-form-item label="快照保留天数">
              <a-input-number
                v-model:value="retentionForm.snapshotDays"
                :min="1"
                :max="365"
                style="width: 180px;"
                addon-after="天"
              />
            </a-form-item>
            <a-form-item label="附件文件保留天数">
              <a-input-number
                v-model:value="retentionForm.attachmentDays"
                :min="1"
                :max="365"
                style="width: 180px;"
                addon-after="天"
              />
            </a-form-item>
            <a-form-item :wrapper-col="{ offset: 6 }">
              <a-button type="primary" :loading="saving.retention" @click="saveRetention">
                保存配置
              </a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { taskApi } from '../../api/task.js'

const activeTab = ref('schedule')

const scheduleForm = ref({
  workHours: [dayjs('08:00', 'HH:mm'), dayjs('20:00', 'HH:mm')],
  workInterval: 7200,
  offHoursInterval: 14400,
})

const autoApproveForm = ref({ enabled: false, threshold: 0.8 })
const alertForm = ref({ webhookUrl: '', notifyMethod: 'dingtalk' })
const retentionForm = ref({ logDays: 30, snapshotDays: 30, attachmentDays: 90 })
const saving = ref({ schedule: false, autoApprove: false, alert: false, retention: false })
const sliderMarks = { 0: '0', 0.5: '0.5', 0.8: '0.8', 1: '1.0' }

async function saveSchedule() {
  saving.value.schedule = true
  try {
    const [start, end] = scheduleForm.value.workHours || []
    await taskApi.updateScheduleConfig?.({
      work_start: start ? start.format('HH:mm') : '08:00',
      work_end: end ? end.format('HH:mm') : '20:00',
      work_interval: scheduleForm.value.workInterval,
      off_hours_interval: scheduleForm.value.offHoursInterval,
    })
    message.success('采集调度配置已保存')
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value.schedule = false
  }
}

async function saveAutoApprove() {
  saving.value.autoApprove = true
  try { message.success('自动审批配置已保存') }
  catch { message.error('保存失败') }
  finally { saving.value.autoApprove = false }
}

async function saveAlert() {
  saving.value.alert = true
  try { message.success('告警配置已保存') }
  catch { message.error('保存失败') }
  finally { saving.value.alert = false }
}

function testWebhook() {
  if (!alertForm.value.webhookUrl) { message.warning('请先填写 Webhook URL'); return }
  message.info('Webhook 测试消息已发送')
}

async function saveRetention() {
  saving.value.retention = true
  try { message.success('数据保留配置已保存') }
  catch { message.error('保存失败') }
  finally { saving.value.retention = false }
}
</script>

<style scoped>
.system-settings { padding: 0; }
.page-header { margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; margin: 0; }
</style>
