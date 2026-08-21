<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>Bug 状态流转规则</span>
        <el-tag type="info" size="small">修改后立即生效（60秒缓存）</el-tag>
      </div>
    </template>

    <el-table :data="transitionRules" stripe row-key="key" :style="{ opacity: workflowLoading ? 0.4 : 1, transition: 'opacity 0.2s ease' }">
      <el-table-column label="从状态" width="130">
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPES[row.from_status]" size="small">
            {{ STATUS_LABELS[row.from_status] || row.from_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="" width="30">
        <template #default>
          <span style="color:var(--text-muted);">→</span>
        </template>
      </el-table-column>
      <el-table-column label="到状态" width="130">
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPES[row.to_status]" size="small">
            {{ STATUS_LABELS[row.to_status] || row.to_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="允许角色" min-width="200">
        <template #default="{ row }">
          <div style="display:flex;flex-wrap:wrap;gap:4px;">
            <el-tag
              v-for="role in ROLE_OPTIONS"
              :key="role.value"
              :type="row.allowed_roles.includes(role.value) ? 'primary' : 'info'"
              :effect="row.allowed_roles.includes(role.value) ? 'dark' : 'plain'"
              size="small"
              style="cursor:pointer;"
              @click="toggleRole(row, role.value)"
            >{{ role.label }}</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="条件约束" width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span style="font-size:12px;color:var(--text-secondary);">
            {{ CONDITION_LABELS[row.condition_type] || '无' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-switch
            v-model="row.is_enabled"
            @change="saveTransitionRule(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="saveTransitionRule(row)">保存</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api'
import { usePermissionConfigStore } from '@/stores/permissionConfig'
import { useRbacStore } from '@/stores/rbac'

const permConfigStore = usePermissionConfigStore()
const rbacStore = useRbacStore()

const transitionRules = ref<any[]>([])
const workflowLoading = ref(false)

const STATUS_LABELS: Record<string, string> = {
  new:         '新建',
  assigned:    '已指派',
  in_progress: '处理中',
  resolved:    '已修复',
  closed:      '已关闭',
  rejected:    '已拒绝',
  reopened:    '重新打开',
}
const STATUS_TYPES: Record<string, string> = {
  new:         'info',
  assigned:    'primary',
  in_progress: 'warning',
  resolved:    'success',
  closed:      '',
  rejected:    'danger',
  reopened:    'warning',
}
const CONDITION_LABELS: Record<string, string> = {
  reporter_or_pm: 'PM 或提交人',
  assignee_only:  'PM 或被指派人',
}
// 流程管理角色按钮：从 rbacStore 动态生成，支持自定义角色
const BUILTIN_ROLE_TYPE: Record<string, string> = {
  viewer: 'info', tester: 'success', developer: 'primary', pm: 'warning',
}
const ROLE_OPTIONS = computed(() =>
  rbacStore.roles.map(r => ({
    value: r.name,
    label: r.label,
    type: BUILTIN_ROLE_TYPE[r.name] ?? 'warning',
  }))
)

async function loadWorkflow() {
  workflowLoading.value = true
  try {
    transitionRules.value = await configApi.listTransitionRules() as any[]
  } catch (e: any) {
    ElMessage.error('加载流程规则失败')
  } finally {
    workflowLoading.value = false
  }
}

onMounted(async () => {
  if (!rbacStore.loaded) await rbacStore.load()
  await loadWorkflow()
})

function toggleRole(row: any, role: string) {
  const idx = row.allowed_roles.indexOf(role)
  if (idx >= 0) {
    row.allowed_roles.splice(idx, 1)
  } else {
    row.allowed_roles.push(role)
  }
}

async function saveTransitionRule(row: any) {
  try {
    await configApi.updateTransitionRule(row.from_status, row.to_status, {
      allowed_roles:   row.allowed_roles,
      required_fields: row.required_fields,
      condition_type:  row.condition_type,
      condition_msg:   row.condition_msg,
      is_enabled:      row.is_enabled,
    })
    ElMessage.success(`已保存：${STATUS_LABELS[row.from_status]} → ${STATUS_LABELS[row.to_status]}`)
    await permConfigStore.reload()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '保存失败')
  }
}
</script>
