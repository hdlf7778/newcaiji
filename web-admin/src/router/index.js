/**
 * Vue Router 路由配置
 *
 * - 所有业务页面挂在 MainLayout 下，使用懒加载（动态 import）
 * - 全局前置守卫：无 token 时重定向到登录页
 * - 未匹配路由统一重定向到仪表盘
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user.js'
import MainLayout from '../layouts/MainLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
      },
      // 采集管理
      {
        path: 'sources',
        name: 'SourceList',
        component: () => import('../views/source/SourceList.vue'),
      },
      {
        path: 'sources/create',
        name: 'SourceCreate',
        component: () => import('../views/source/SourceCreate.vue'),
      },
      {
        path: 'sources/import',
        name: 'SourceImport',
        component: () => import('../views/source/SourceImport.vue'),
      },
      {
        path: 'sources/:id',
        name: 'SourceDetail',
        component: () => import('../views/source/SourceDetail.vue'),
      },
      {
        path: 'rules',
        name: 'RuleList',
        component: () => import('../views/rule/RuleList.vue'),
      },
      {
        path: 'rules/:id/edit',
        name: 'RuleEdit',
        component: () => import('../views/rule/RuleEdit.vue'),
      },
      {
        path: 'templates',
        name: 'TemplateList',
        component: () => import('../views/template/TemplateList.vue'),
      },
      {
        path: 'templates/:id',
        name: 'TemplateDetail',
        component: () => import('../views/template/TemplateDetail.vue'),
      },
      {
        path: 'tasks',
        name: 'TaskList',
        component: () => import('../views/task/TaskList.vue'),
      },
      {
        path: 'dead-letters',
        name: 'DeadLetterList',
        component: () => import('../views/task/DeadLetterList.vue'),
      },
      // 内容
      {
        path: 'articles',
        name: 'ArticleList',
        component: () => import('../views/article/ArticleList.vue'),
      },
      {
        path: 'articles/:id',
        name: 'ArticleDetail',
        component: () => import('../views/article/ArticleDetail.vue'),
      },
      // 审核
      {
        path: 'review',
        name: 'ReviewWorkbench',
        component: () => import('../views/review/ReviewWorkbench.vue'),
      },
      // 系统
      {
        path: 'workers',
        name: 'WorkerStatus',
        meta: { requiresAuth: true, roles: ['admin'] },
        component: () => import('../views/system/WorkerStatus.vue'),
      },
      {
        path: 'settings',
        name: 'Settings',
        meta: { requiresAuth: true, roles: ['admin'] },
        component: () => import('../views/system/Settings.vue'),
      },
      {
        path: 'guide',
        name: 'UserGuide',
        component: () => import('../views/system/UserGuide.vue'),
      },
      {
        path: 'users',
        name: 'UserManage',
        meta: { requiresAuth: true, roles: ['admin'] },
        component: () => import('../views/system/UserManage.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局路由守卫：未登录时拦截并跳转到登录页；检查角色权限
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
    return
  }
  // 路由级 RBAC：检查角色权限
  if (to.meta.roles) {
    const userStore = useUserStore()
    if (!to.meta.roles.includes(userStore.role)) {
      next({ name: 'Dashboard' })
      return
    }
  }
  next()
})

export default router
