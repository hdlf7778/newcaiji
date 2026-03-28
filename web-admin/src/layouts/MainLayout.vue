<!--
  主布局组件（MainLayout）

  结构：左侧固定侧边栏 + 右侧内容区（顶部 Header + 路由视图）
  功能：
    - 侧边栏菜单自动高亮当前路由、展开所属子菜单
    - 面包屑根据路由路径动态生成
    - 死信队列和待审核数量在菜单项上以 Badge 展示（当前为占位值）
-->
<template>
  <a-layout style="min-height: 100vh">
    <!-- Sidebar -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      :trigger="null"
      collapsible
      :width="220"
      theme="dark"
      style="overflow: auto; height: 100vh; position: fixed; left: 0; top: 0; bottom: 0"
    >
      <!-- Logo -->
      <div class="logo">
        <DatabaseOutlined class="logo-icon" />
        <span v-if="!collapsed" class="logo-text">源画像库</span>
      </div>

      <!-- Menu -->
      <a-menu
        v-model:selectedKeys="selectedKeys"
        v-model:openKeys="openKeys"
        theme="dark"
        mode="inline"
        @click="handleMenuClick"
      >
        <!-- 监控仪表盘 -->
        <a-menu-item key="/dashboard">
          <template #icon><DashboardOutlined /></template>
          监控仪表盘
        </a-menu-item>

        <!-- 采集管理 -->
        <a-sub-menu key="collection">
          <template #icon><CloudDownloadOutlined /></template>
          <template #title>采集管理</template>
          <a-menu-item key="/sources">
            <template #icon><UnorderedListOutlined /></template>
            采集源列表
          </a-menu-item>
          <a-menu-item key="/rules">
            <template #icon><FilterOutlined /></template>
            规则管理
          </a-menu-item>
          <a-menu-item key="/templates">
            <template #icon><FileTextOutlined /></template>
            模板列表
          </a-menu-item>
          <a-menu-item key="/tasks">
            <template #icon><ScheduleOutlined /></template>
            任务列表
          </a-menu-item>
          <a-menu-item key="/dead-letters">
            <template #icon>
              <a-badge :count="deadLetterCount" :offset="[8, 0]" size="small">
                <WarningOutlined />
              </a-badge>
            </template>
            死信队列
          </a-menu-item>
        </a-sub-menu>

        <!-- 内容 -->
        <a-sub-menu key="content">
          <template #icon><FileOutlined /></template>
          <template #title>内容</template>
          <a-menu-item key="/articles">
            <template #icon><ReadOutlined /></template>
            文章列表
          </a-menu-item>
        </a-sub-menu>

        <!-- 审核 -->
        <a-sub-menu key="audit">
          <template #icon><AuditOutlined /></template>
          <template #title>审核</template>
          <a-menu-item key="/review">
            <template #icon>
              <a-badge :count="reviewCount" :offset="[8, 0]" size="small">
                <CheckCircleOutlined />
              </a-badge>
            </template>
            审核工作台
          </a-menu-item>
        </a-sub-menu>

        <!-- 系统 -->
        <a-sub-menu key="system">
          <template #icon><SettingOutlined /></template>
          <template #title>系统</template>
          <a-menu-item key="/workers">
            <template #icon><ClusterOutlined /></template>
            Worker 状态
          </a-menu-item>
          <a-menu-item key="/settings">
            <template #icon><ToolOutlined /></template>
            系统设置
          </a-menu-item>
          <a-menu-item key="/guide">
            <template #icon><QuestionCircleOutlined /></template>
            使用说明
          </a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>

    <!-- Main content area -->
    <a-layout :style="{ marginLeft: collapsed ? '80px' : '220px', transition: 'all 0.2s' }">
      <!-- Header -->
      <a-layout-header
        style="
          background: #fff;
          padding: 0 24px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          box-shadow: 0 1px 4px rgba(0,21,41,.08);
          position: sticky;
          top: 0;
          z-index: 10;
        "
      >
        <div style="display: flex; align-items: center; gap: 16px">
          <!-- Collapse toggle -->
          <component
            :is="collapsed ? MenuUnfoldOutlined : MenuFoldOutlined"
            style="font-size: 18px; cursor: pointer; color: #595959"
            @click="toggleCollapsed"
          />
          <!-- Breadcrumb -->
          <a-breadcrumb>
            <a-breadcrumb-item v-for="item in breadcrumb" :key="item.path">
              {{ item.title }}
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>

        <!-- User area -->
        <div style="display: flex; align-items: center; gap: 12px">
          <a-avatar style="background-color: #1677ff">
            {{ username ? username[0]?.toUpperCase() : 'U' }}
          </a-avatar>
          <span style="color: #262626; font-size: 14px">{{ username }}</span>
          <a-button type="text" size="small" @click="handleLogout">
            <template #icon><LogoutOutlined /></template>
            退出
          </a-button>
        </div>
      </a-layout-header>

      <!-- Content -->
      <a-layout-content style="margin: 24px; min-height: calc(100vh - 64px - 48px)">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user.js'
import { useAppStore } from '../stores/app.js'
import {
  DatabaseOutlined,
  DashboardOutlined,
  CloudDownloadOutlined,
  UnorderedListOutlined,
  FilterOutlined,
  FileTextOutlined,
  ScheduleOutlined,
  WarningOutlined,
  FileOutlined,
  ReadOutlined,
  AuditOutlined,
  CheckCircleOutlined,
  SettingOutlined,
  ClusterOutlined,
  ToolOutlined,
  QuestionCircleOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
} from '@ant-design/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const appStore = useAppStore()

const collapsed = ref(appStore.sidebarCollapsed)
const selectedKeys = ref([route.path])
const openKeys = ref([])

const username = computed(() => userStore.username)
const breadcrumb = computed(() => appStore.breadcrumb)

// 侧边栏菜单 Badge 数字（当前为硬编码占位，应改为从 API 拉取）
const deadLetterCount = ref(0)
const reviewCount = ref(0)

// 路由路径 → 面包屑标题的映射表
const routeTitles = {
  '/dashboard': '监控仪表盘',
  '/sources': '采集源列表',
  '/sources/create': '采集源新增',
  '/rules': '规则管理',
  '/templates': '模板列表',
  '/tasks': '任务列表',
  '/dead-letters': '死信队列',
  '/articles': '文章列表',
  '/review': '审核工作台',
  '/workers': 'Worker 状态',
  '/settings': '系统设置',
  '/guide': '使用说明',
}

function updateBreadcrumb(path) {
  const title = routeTitles[path] || path
  appStore.setBreadcrumb([{ title: '首页', path: '/' }, { title, path }])
}

// Keep selectedKeys in sync with route
watch(
  () => route.path,
  (path) => {
    selectedKeys.value = [path]
    updateBreadcrumb(path)
  },
  { immediate: true }
)

// Auto-expand the parent sub-menu based on current path
watch(
  () => route.path,
  (path) => {
    if (path.startsWith('/sources') || path.startsWith('/rules') || path.startsWith('/templates') || path.startsWith('/tasks') || path.startsWith('/dead-letters')) {
      openKeys.value = ['collection']
    } else if (path.startsWith('/articles')) {
      openKeys.value = ['content']
    } else if (path.startsWith('/review')) {
      openKeys.value = ['audit']
    } else if (path.startsWith('/workers') || path.startsWith('/settings') || path.startsWith('/guide')) {
      openKeys.value = ['system']
    }
  },
  { immediate: true }
)

function handleMenuClick({ key }) {
  router.push(key)
}

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  appStore.toggleSidebar()
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #002140;
  overflow: hidden;
}
.logo-icon {
  font-size: 20px;
  color: #1677ff;
  flex-shrink: 0;
}
.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
}
</style>
