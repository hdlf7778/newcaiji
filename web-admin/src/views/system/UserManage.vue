<template>
  <div class="user-manage">
    <div class="page-header">
      <h2 class="page-title">用户管理</h2>
      <a-button type="primary" @click="openAddModal">+ 新增用户</a-button>
    </div>

    <a-card :body-style="{ padding: 0 }">
      <a-table
        :columns="columns"
        :data-source="users"
        :loading="loading"
        row-key="id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'role'">
            <a-tag :color="record.role === 'admin' ? 'red' : 'blue'">
              {{ record.role === 'admin' ? '管理员' : '普通用户' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : 'default'">
              {{ record.status === 'active' ? '正常' : '禁用' }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" @click="openEditRole(record)">修改角色</a-button>
              <a-button size="small" @click="resetPassword(record)">重置密码</a-button>
              <a-button
                size="small"
                :danger="record.status === 'active'"
                @click="toggleStatus(record)"
              >
                {{ record.status === 'active' ? '禁用' : '启用' }}
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- Add user modal -->
    <a-modal
      v-model:open="addModalVisible"
      title="新增用户"
      :confirm-loading="submitting"
      @ok="submitAddUser"
      @cancel="resetAddForm"
    >
      <a-form :model="addForm" :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }" style="margin-top: 16px;">
        <a-form-item label="用户名" required>
          <a-input v-model:value="addForm.username" placeholder="请输入用户名" />
        </a-form-item>
        <a-form-item label="密码" required>
          <a-input-password v-model:value="addForm.password" placeholder="请输入密码" />
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model:value="addForm.role">
            <a-select-option value="admin">管理员</a-select-option>
            <a-select-option value="user">普通用户</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Edit role modal -->
    <a-modal
      v-model:open="editRoleVisible"
      title="修改角色"
      @ok="submitEditRole"
      @cancel="editRoleVisible = false"
    >
      <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 16 }" style="margin-top: 16px;">
        <a-form-item label="用户名">
          <span>{{ editTarget?.username }}</span>
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model:value="editRoleValue">
            <a-select-option value="admin">管理员</a-select-option>
            <a-select-option value="user">普通用户</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'

const loading = ref(false)
const users = ref([
  { id: 1, username: 'admin', role: 'admin', last_login: '2026-03-27 10:00', status: 'active' },
  { id: 2, username: 'operator1', role: 'user', last_login: '2026-03-26 14:23', status: 'active' },
])

const addModalVisible = ref(false)
const submitting = ref(false)
const addForm = ref({ username: '', password: '', role: 'user' })

const editRoleVisible = ref(false)
const editTarget = ref(null)
const editRoleValue = ref('user')

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '角色', key: 'role', dataIndex: 'role', width: 100 },
  { title: '最后登录', dataIndex: 'last_login', key: 'last_login', width: 180 },
  { title: '状态', key: 'status', dataIndex: 'status', width: 80 },
  { title: '操作', key: 'actions', width: 220 },
]

function openAddModal() {
  addModalVisible.value = true
}

function resetAddForm() {
  addForm.value = { username: '', password: '', role: 'user' }
}

async function submitAddUser() {
  if (!addForm.value.username || !addForm.value.password) {
    message.warning('用户名和密码不能为空')
    return
  }
  submitting.value = true
  try {
    const newUser = {
      id: Date.now(),
      username: addForm.value.username,
      role: addForm.value.role,
      last_login: '—',
      status: 'active',
    }
    users.value.push(newUser)
    message.success('用户创建成功')
    addModalVisible.value = false
    resetAddForm()
  } catch (e) {
    message.error('创建失败')
  } finally {
    submitting.value = false
  }
}

function openEditRole(record) {
  editTarget.value = record
  editRoleValue.value = record.role
  editRoleVisible.value = true
}

function submitEditRole() {
  if (editTarget.value) {
    const idx = users.value.findIndex(u => u.id === editTarget.value.id)
    if (idx !== -1) {
      users.value[idx] = { ...users.value[idx], role: editRoleValue.value }
    }
    message.success('角色已更新')
  }
  editRoleVisible.value = false
}

function resetPassword(record) {
  message.info(`已向 ${record.username} 发送密码重置邮件`)
}

function toggleStatus(record) {
  const idx = users.value.findIndex(u => u.id === record.id)
  if (idx !== -1) {
    const newStatus = users.value[idx].status === 'active' ? 'disabled' : 'active'
    users.value[idx] = { ...users.value[idx], status: newStatus }
    message.success(`用户 ${record.username} 已${newStatus === 'active' ? '启用' : '禁用'}`)
  }
}

onMounted(() => {
  // users are pre-loaded as mock data; replace with API call if available
})
</script>

<style scoped>
.user-manage {
  padding: 0;
}

.page-header {
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
</style>
