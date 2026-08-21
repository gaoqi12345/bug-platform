<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>角色列表</span>
        <el-button type="primary" size="small" @click="openCreateRole">+ 新建角色</el-button>
      </div>
    </template>

    <el-table :data="rbacStore.roles" stripe :style="{ opacity: rolesLoading ? 0.4 : 1, transition: 'opacity 0.2s ease' }">
      <el-table-column label="角色" width="200">
        <template #default="{ row }">
          <el-tag :color="row.color" effect="dark" style="border:none">{{ row.label }}</el-tag>
          <span style="color:var(--text-muted); font-size:12px; margin-left:6px;">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="描述" show-overflow-tooltip>
        <template #default="{ row }">{{ row.description || '—' }}</template>
      </el-table-column>
      <el-table-column label="权限点数量" width="110">
        <template #default="{ row }">{{ row.permissions.length }}</template>
      </el-table-column>
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_builtin ? 'info' : 'success'" size="small">
            {{ row.is_builtin ? '内置' : '自定义' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="openEditRole(row)">编辑权限</el-button>
          <el-button size="small" type="danger" plain :disabled="row.is_builtin" @click="deleteRole(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 新建/编辑角色对话框 -->
  <el-dialog v-model="roleDialog" :title="roleDialogTitle" width="640px" @closed="resetRoleForm">
    <el-form :model="roleForm" label-width="90px">
      <el-form-item label="角色标识" v-if="!editingRole">
        <el-input v-model="roleForm.name" placeholder="如：architect（小写字母开头，字母数字下划线，2-30位）" />
      </el-form-item>
      <el-form-item label="显示名称">
        <el-input v-model="roleForm.label" placeholder="如：架构师" />
      </el-form-item>
      <el-form-item label="颜色">
        <el-color-picker v-model="roleForm.color" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="roleForm.description" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
      <el-form-item label="权限点">
        <div style="width:100%;">
          <div
            v-for="(perms, module) in rbacStore.permissionsByModule"
            :key="module"
            class="permission-module"
          >
            <div class="permission-module__title">
              {{ MODULE_LABELS[module] || module }}
            </div>
            <el-checkbox-group v-model="roleForm.permissions">
              <el-checkbox v-for="p in perms" :key="p.code" :label="p.code" :value="p.code">
                {{ p.label }}
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="roleDialog = false">取消</el-button>
      <el-button type="primary" :loading="savingRole" @click="submitRole">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { rolesApi } from '@/api'
import { useRbacStore } from '@/stores/rbac'

const rbacStore = useRbacStore()

const rolesLoading = ref(false)
const editingRole  = ref<any>(null)
const savingRole   = ref(false)

const MODULE_LABELS: Record<string, string> = {
  bug:        'Bug 管理',
  attachment: '附件',
  testcase:   '测试用例',
  version:    '版本',
  stats:      '统计报表',
  project:    '项目',
}

const roleForm = reactive({ name: '', label: '', color: '#409EFF', description: '', permissions: [] as string[] })

const roleDialogTitle = computed(() =>
  editingRole.value ? `编辑角色权限 — ${editingRole.value.label}` : '新建角色'
)

async function loadRoles() {
  rolesLoading.value = true
  try {
    await rbacStore.load()
  } catch {
    ElMessage.error('加载角色失败')
  } finally {
    rolesLoading.value = false
  }
}

onMounted(() => {
  if (!rbacStore.loaded) loadRoles()
})

function openCreateRole() {
  editingRole.value = null
  roleDialog.value = true
}

function openEditRole(row: any) {
  editingRole.value = row
  Object.assign(roleForm, {
    name: row.name,
    label: row.label,
    color: row.color,
    description: row.description || '',
    permissions: [...row.permissions],
  })
  roleDialog.value = true
}

function resetRoleForm() {
  editingRole.value = null
  Object.assign(roleForm, { name: '', label: '', color: '#409EFF', description: '', permissions: [] })
}

async function submitRole() {
  if (!roleForm.label.trim()) { ElMessage.warning('请输入显示名称'); return }
  if (!editingRole.value && !roleForm.name.trim()) { ElMessage.warning('请输入角色标识'); return }
  savingRole.value = true
  try {
    if (editingRole.value) {
      await rolesApi.updateRole(editingRole.value.id, {
        label: roleForm.label,
        color: roleForm.color,
        description: roleForm.description,
        permissions: roleForm.permissions,
      })
      ElMessage.success('角色已更新')
    } else {
      await rolesApi.createRole({
        name: roleForm.name,
        label: roleForm.label,
        color: roleForm.color,
        description: roleForm.description,
        permissions: roleForm.permissions,
      })
      ElMessage.success('角色创建成功')
    }
    roleDialog.value = false
    await rbacStore.reload()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '保存失败')
  } finally {
    savingRole.value = false
  }
}

async function deleteRole(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.label}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await rolesApi.deleteRole(row.id)
    ElMessage.success('角色已删除')
    await rbacStore.reload()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '删除失败')
  }
}
</script>

<style scoped>
.permission-module {
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-subtle);
}

.permission-module__title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--text-secondary);
}
</style>
