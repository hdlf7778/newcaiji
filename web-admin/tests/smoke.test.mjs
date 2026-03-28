/**
 * E2E Smoke Test — 验证所有页面能正常登录、导航、渲染
 *
 * 运行: cd web-admin && node tests/smoke.test.mjs
 * 前提: Java后端(8080) + Vue前端(5173) 均已启动
 */
import { chromium } from 'playwright'

const BASE = 'http://localhost:5173'
const CREDENTIALS = { username: 'admin', password: 'admin123' }

const PAGES = [
  { path: '/dashboard',    name: '监控仪表盘', mustHave: '.stat-card' },
  { path: '/sources',      name: '采集源列表', mustHave: '.ant-table' },
  { path: '/rules',        name: '规则管理',   mustHave: '.ant-table' },
  { path: '/templates',    name: '模板列表',   mustHave: '.ant-layout-content' },
  { path: '/tasks',        name: '任务列表',   mustHave: '.ant-table' },
  { path: '/dead-letters', name: '死信队列',   mustHave: '.ant-table' },
  { path: '/articles',     name: '文章列表',   mustHave: '.ant-table' },
  { path: '/review',       name: '审核工作台', mustHave: '.ant-layout-content' },
  { path: '/workers',      name: 'Worker状态', mustHave: '.ant-table' },
  { path: '/settings',     name: '系统设置',   mustHave: '.ant-layout-content' },
]

let passed = 0
let failed = 0

function assert(cond, msg) {
  if (cond) { passed++; console.log(`  ✅ ${msg}`) }
  else      { failed++; console.log(`  ❌ ${msg}`) }
}

async function run() {
  const browser = await chromium.launch({ headless: true })

  // ---- Test 1: Login ----
  console.log('\n=== Test 1: Login ===')
  const loginPage = await browser.newPage()
  await loginPage.goto(`${BASE}/login`)
  await loginPage.waitForLoadState('networkidle')

  assert(loginPage.url().includes('/login'), 'Login page loads')

  await loginPage.fill('input[placeholder*="用户"]', CREDENTIALS.username)
  await loginPage.fill('input[type="password"]', CREDENTIALS.password)
  await loginPage.click('button[type="submit"]')
  await loginPage.waitForTimeout(3000)

  assert(loginPage.url().includes('/dashboard'), `Redirect to dashboard after login (got ${loginPage.url()})`)

  const hasSidebar = await loginPage.$('.ant-layout-sider') !== null
  assert(hasSidebar, 'Sidebar rendered')

  const hasDashboard = await loginPage.$('.stat-card') !== null
  assert(hasDashboard, 'Dashboard stat cards rendered')

  // Get token for subsequent pages
  const token = await loginPage.evaluate(() => localStorage.getItem('token'))
  assert(token && token.length > 20, `Token stored (len=${token?.length})`)

  await loginPage.close()

  // ---- Test 2: All pages navigation ----
  console.log('\n=== Test 2: Page Navigation (10 pages) ===')
  for (const { path, name, mustHave } of PAGES) {
    const page = await browser.newPage()
    const errors = []
    page.on('pageerror', err => errors.push(String(err)))

    // Set auth
    await page.goto(`${BASE}/login`)
    await page.evaluate(t => {
      localStorage.setItem('token', t)
      localStorage.setItem('username', 'admin')
      localStorage.setItem('role', 'admin')
    }, token)

    await page.goto(`${BASE}${path}`)
    await page.waitForTimeout(2500)

    const noJsError = errors.length === 0
    const hasElement = await page.$(mustHave) !== null
    const hasLayout  = await page.$('.ant-layout-sider') !== null

    if (noJsError && hasElement && hasLayout) {
      console.log(`  ✅ ${name} (${path})`)
      passed++
    } else {
      console.log(`  ❌ ${name} (${path})`)
      if (!noJsError)  console.log(`     JS Error: ${errors[0]?.substring(0, 100)}`)
      if (!hasElement)  console.log(`     Missing: ${mustHave}`)
      if (!hasLayout)   console.log(`     Missing: sidebar layout`)
      failed++
    }

    await page.close()
  }

  // ---- Test 3: API response contract ----
  console.log('\n=== Test 3: API Response Contract ===')
  const apiPage = await browser.newPage()
  await apiPage.goto(`${BASE}/login`)
  await apiPage.evaluate(t => localStorage.setItem('token', t), token)

  // Test list API returns {records: Array, total: number}
  const listRes = await apiPage.evaluate(async () => {
    const r = await fetch('/api/sources?page=1&pageSize=5', {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    return r.json()
  })
  assert(listRes.success === true, 'sources API success=true')
  assert(Array.isArray(listRes.data?.records), `sources API data.records is Array (got ${typeof listRes.data?.records})`)
  assert(typeof listRes.data?.total === 'number', `sources API data.total is number (got ${listRes.data?.total})`)

  // Test dashboard API returns flat object with snake_case keys
  const dashRes = await apiPage.evaluate(async () => {
    const r = await fetch('/api/monitor/dashboard', {
      headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
    })
    return r.json()
  })
  assert(dashRes.success === true, 'dashboard API success=true')
  assert('active_sources' in (dashRes.data || {}), 'dashboard has active_sources (snake_case)')
  assert('today_articles' in (dashRes.data || {}), 'dashboard has today_articles (snake_case)')

  await apiPage.close()
  await browser.close()

  // ---- Summary ----
  console.log(`\n${'='.repeat(50)}`)
  console.log(`Smoke Test: ${passed} passed, ${failed} failed`)
  if (failed > 0) process.exit(1)
  else console.log('All smoke tests passed!')
}

run().catch(err => {
  console.error('Smoke test crashed:', err)
  process.exit(1)
})
