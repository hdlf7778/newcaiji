/**
 * 采集源信息缓存 composable
 * 根据当前页数据中的 source_id，按需加载采集源的 name 和 column_name
 * 使用 Promise.all 并发请求替代逐条串行
 */
import { ref } from 'vue'
import request from '../api/request.js'

// 全局缓存（跨组件共享）
const cache = ref({})

export function useSourceInfo() {
  /**
   * 批量加载 source_id 对应的名称信息
   * @param {number[]} sourceIds - 需要查询的 source_id 列表
   */
  async function loadByIds(sourceIds) {
    const missingIds = [...new Set(sourceIds.filter(id => id && !cache.value[id]))]
    if (!missingIds.length) return

    // 并发请求（替代逐条串行的 N+1 模式）
    const results = await Promise.allSettled(
      missingIds.map(id => request.get(`/api/sources/${id}`))
    )
    for (let i = 0; i < missingIds.length; i++) {
      const r = results[i]
      if (r.status === 'fulfilled' && r.value) {
        cache.value[missingIds[i]] = {
          name: r.value.name,
          column_name: r.value.column_name,
        }
      }
    }
  }

  /**
   * 从表格数据中提取 source_id 并加载
   * @param {Array} tableData - 表格行数据（需包含 source_id 字段）
   */
  async function loadForTable(tableData) {
    const ids = tableData.map(r => r.source_id).filter(Boolean)
    await loadByIds(ids)
  }

  function getName(id) {
    return cache.value[id]?.name || `#${id}`
  }

  function getColumnName(id) {
    return cache.value[id]?.column_name || '—'
  }

  return { sourceInfoMap: cache, loadForTable, loadByIds, getName, getColumnName }
}
