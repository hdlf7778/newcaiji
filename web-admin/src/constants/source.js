/**
 * 采集源相关的共享常量和工具函数
 * 所有 Vue 页面统一从此文件导入，避免重复定义
 */

// 模板类型映射（兼容大小写 key）
export const TEMPLATE_MAP = {
  STATIC_LIST: { letter: 'A', label: '静态列表', color: 'purple' },
  IFRAME_LOADER: { letter: 'B', label: 'iframe加载', color: 'orange' },
  API_JSON: { letter: 'C', label: 'API接口', color: 'blue' },
  WECHAT_ARTICLE: { letter: 'D', label: '微信公众号', color: 'green' },
  SEARCH_DISCOVERY: { letter: 'E', label: '搜索监控', color: 'cyan' },
  AUTH_REQUIRED: { letter: 'F', label: '登录态', color: 'red' },
  SPA_RENDER: { letter: 'G', label: 'SPA渲染', color: 'volcano' },
  RSS_FEED: { letter: 'H', label: 'RSS订阅', color: 'lime' },
  GOV_CLOUD_PLATFORM: { letter: 'I', label: '政务云', color: 'geekblue' },
  CAPTURED_API: { letter: 'J', label: '抓包API', color: 'default' },
}

export function templateLabel(type) {
  if (!type) return '未识别模版'
  const key = type.toUpperCase().replace(/-/g, '_')
  const t = TEMPLATE_MAP[key]
  return t ? `${t.letter} ${t.label}` : type
}

export function templateColor(type) {
  if (!type) return 'warning'
  const key = type.toUpperCase().replace(/-/g, '_')
  return TEMPLATE_MAP[key]?.color || 'default'
}

// 状态映射（13 个完整状态）
export const STATUS_MAP = {
  PENDING_DETECT: { label: '待检测', color: 'default' },
  DETECTING: { label: '检测中', color: 'processing' },
  DETECTED: { label: '检测完成', color: 'cyan' },
  DETECT_FAILED: { label: '检测失败', color: 'error' },
  TRIAL: { label: '试采中', color: 'processing' },
  TRIAL_PASSED: { label: '试采通过', color: 'cyan' },
  TRIAL_FAILED: { label: '试采失败', color: 'error' },
  PENDING_REVIEW: { label: '待审核', color: 'warning' },
  APPROVED: { label: '已审批', color: 'blue' },
  ACTIVE: { label: '活跃', color: 'success' },
  PAUSED: { label: '暂停', color: 'default' },
  ERROR: { label: '异常', color: 'error' },
  RETIRED: { label: '退役', color: 'default' },
}

export function statusLabel(status) {
  const key = (status || '').toUpperCase()
  return STATUS_MAP[key]?.label || status
}

export function statusColor(status) {
  const key = (status || '').toUpperCase()
  return STATUS_MAP[key]?.color || 'default'
}

// 试采评分颜色
export function scoreColor(score) {
  if (score == null) return 'default'
  if (score >= 0.8) return 'green'
  if (score >= 0.6) return 'orange'
  return 'red'
}

// 评分阈值常量
export const SCORE_HIGH = 0.8
export const SCORE_MEDIUM = 0.6
