import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const breadcrumb = ref([])

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setBreadcrumb(items) {
    breadcrumb.value = items
  }

  return { sidebarCollapsed, breadcrumb, toggleSidebar, setBreadcrumb }
})
