<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>用户列表</span>
        <div style="display:flex;gap:8px;">
          <el-button size="small" @click="openImportUser">导入用户</el-button>
          <el-button type="primary" size="small" @click="openCreateUser">+ 新建用户</el-button>
        </div>
      </div>
    </template>

    <el-table :data="users" stripe
      :row-class-name="({ row }: { row: any }) => row.is_active === false ? 'row-deactivated' : ''"
      :style="{ opacity: usersLoading ? 0.4 : 1, transition: 'opacity 0.2s ease' }">
      <el-table-column prop="id"           label="ID"   width="70" />
      <el-table-column prop="display_name" label="姓名" />
      <el-table-column prop="email"        label="邮箱" show-overflow-tooltip />
      <el-table-column prop="feishu_open_id" label="飞书 open_id" show-overflow-tooltip />
      <el-table-column label="超管" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_super_admin ? 'danger' : 'info'" size="small">
            {{ row.is_super_admin ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active !== false ? 'success' : 'info'" size="small">
            {{ row.is_active !== false ? '正常' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="openEditUser(row)">编辑</el-button>
          <el-button v-if="row.is_active !== false" size="small" type="warning" plain
            :disabled="row.id === auth.user?.id"
            @click="deactivateUser(row)">停用</el-button>
          <el-button v-else size="small" type="success" plain
            @click="activateUser(row)">启用</el-button>
          <el-button size="small" type="danger" plain
            :disabled="row.id === auth.user?.id"
            @click="confirmDeleteUser(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 导入用户对话框 -->
  <el-dialog v-model="importUserDialog" title="批量导入用户" width="680px" @closed="resetImportDialog">
    <div style="margin-bottom:16px;">
      <el-steps :active="importStep" simple>
        <el-step title="上传文件" />
        <el-step title="预览数据" />
        <el-step title="导入结果" />
      </el-steps>
    </div>

    <!-- Step 0: 上传 -->
    <div v-if="importStep === 0">
      <el-alert type="info" :closable="false" style="margin-bottom:16px;">
        <template #default>
          <div>支持 <strong>CSV</strong> 或 <strong>TXT</strong>（逗号分隔），每行格式：</div>
          <code style="font-size:12px;background:var(--bg-surface-2);padding:2px 6px;border-radius:3px;">
            邮箱,显示名称,初始密码[,飞书open_id]
          </code>
          <div style="margin-top:6px;">首行若为表头（含"邮箱"或"email"）将自动跳过。</div>
        </template>
      </el-alert>
      <div style="display:flex;gap:10px;margin-bottom:16px;">
        <el-button size="small" @click="downloadTemplate">
          <el-icon style="margin-right:4px;"><Download /></el-icon>下载模板
        </el-button>
      </div>
      <el-upload
        drag
        :auto-upload="false"
        accept=".csv,.txt"
        :limit="1"
        :on-change="onImportFileChange"
        :on-remove="() => { importRawRows = [] }"
        :file-list="importFileList"
      >
        <el-icon style="font-size:40px;color:var(--text-muted);"><Upload /></el-icon>
        <div style="margin-top:8px;color:var(--text-secondary);">将 CSV / TXT 文件拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div style="font-size:12px;color:var(--text-muted);">仅支持 .csv / .txt，文件大小不超过 1MB</div>
        </template>
      </el-upload>
    </div>

    <!-- Step 1: 预览 -->
    <div v-if="importStep === 1">
      <el-alert
        v-if="importParseErrors.length"
        type="warning"
        :closable="false"
        style="margin-bottom:12px;"
        :title="`${importParseErrors.length} 行格式有误，已过滤（见下方）`"
      />
      <div style="margin-bottom:8px;color:var(--text-secondary);font-size:13px;">
        共解析到 <strong>{{ importPreviewRows.length }}</strong> 条有效记录，确认后导入：
      </div>
      <el-table :data="importPreviewRows" max-height="320" stripe size="small">
        <el-table-column prop="email"        label="邮箱"     min-width="180" show-overflow-tooltip />
        <el-table-column prop="display_name" label="显示名称" width="120" />
        <el-table-column label="密码"        width="100">
          <template #default="{ row }">
            <span style="color:var(--text-muted);">{{ '*'.repeat(Math.min(row.password.length, 8)) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="feishu_open_id" label="飞书 open_id" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.feishu_open_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row._error" type="danger" size="small">错误</el-tag>
            <el-tag v-else type="success" size="small">待导入</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="importParseErrors.length" style="margin-top:12px;">
        <div style="font-size:12px;color:var(--color-warning);margin-bottom:4px;">跳过的行：</div>
        <div v-for="(e, i) in importParseErrors" :key="i"
          style="font-size:12px;color:var(--text-muted);font-family:monospace;">
          第 {{ e.line }} 行：{{ e.raw }} — {{ e.reason }}
        </div>
      </div>
    </div>

    <!-- Step 2: 结果 -->
    <div v-if="importStep === 2">
      <el-result
        v-if="importResult"
        :icon="importResult.errors?.length ? 'warning' : 'success'"
        :title="importResult.errors?.length ? '导入完成（有部分错误）' : '导入成功'"
      >
        <template #sub-title>
          <div style="font-size:14px;line-height:2;">
            <div>✅ 成功创建：<strong>{{ importResult.created }}</strong> 人</div>
            <div>⏭ 跳过（邮箱已存在）：<strong>{{ importResult.skipped }}</strong> 人</div>
            <div v-if="importResult.errors?.length">
              ❌ 错误：<strong>{{ importResult.errors.length }}</strong> 条
            </div>
          </div>
          <div v-if="importResult.errors?.length" style="margin-top:8px;text-align:left;">
            <div v-for="e in importResult.errors" :key="e.email"
              style="font-size:12px;color:var(--color-danger);">{{ e.email }}：{{ e.reason }}</div>
          </div>
        </template>
      </el-result>
    </div>

    <template #footer>
      <el-button @click="importUserDialog = false">{{ importStep === 2 ? '关闭' : '取消' }}</el-button>
      <el-button v-if="importStep === 0" type="primary"
        :disabled="importPreviewRows.length === 0"
        @click="importStep = 1">
        下一步（预览 {{ importPreviewRows.length }} 条）
      </el-button>
      <el-button v-if="importStep === 1" @click="importStep = 0">上一步</el-button>
      <el-button v-if="importStep === 1" type="primary"
        :loading="saving"
        :disabled="importPreviewRows.length === 0"
        @click="submitImport">
        确认导入 {{ importPreviewRows.length }} 位用户
      </el-button>
    </template>
  </el-dialog>

  <!-- 编辑用户对话框 -->
  <el-dialog v-model="editUserDialog" title="编辑用户" width="460px" @closed="resetEditUserForm">
    <el-form :model="editUserForm" :rules="editUserRules" ref="editUserFormRef" label-width="110px">
      <el-form-item label="邮箱">
        <el-input :value="editUserForm.email" disabled />
      </el-form-item>
      <el-form-item label="显示名称" prop="display_name">
        <el-input v-model="editUserForm.display_name" placeholder="张三" />
      </el-form-item>
      <el-form-item label="飞书 open_id">
        <el-input v-model="editUserForm.feishu_open_id" placeholder="ou_xxx（用于飞书通知）" />
      </el-form-item>
      <el-form-item label="超级管理员">
        <el-switch v-model="editUserForm.is_super_admin"
          :disabled="editUserForm.id === auth.user?.id" />
        <span v-if="editUserForm.id === auth.user?.id"
          style="font-size:12px;color:var(--text-muted);margin-left:8px;">不能修改自己的超管权限</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editUserDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submitEditUser">保存</el-button>
    </template>
  </el-dialog>

  <!-- 新建用户对话框 -->
  <el-dialog v-model="userDialog" title="新建用户" width="460px" @closed="resetUserForm">
    <el-form :model="userForm" :rules="userRules" ref="userFormRef" label-width="110px">
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="userForm.email" placeholder="user@company.com" />
      </el-form-item>
      <el-form-item label="显示名称" prop="display_name">
        <el-input v-model="userForm.display_name" placeholder="张三" />
      </el-form-item>
      <el-form-item label="初始密码" prop="password">
        <el-input v-model="userForm.password" type="password" show-password placeholder="至少8位" />
      </el-form-item>
      <el-form-item label="飞书 open_id">
        <el-input v-model="userForm.feishu_open_id" placeholder="ou_xxx（用于飞书通知）" />
      </el-form-item>
      <el-form-item label="超级管理员">
        <el-switch v-model="userForm.is_super_admin" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="userDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submitUser">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { userApi } from '@/api'
import { Download, Upload } from '@element-plus/icons-vue'

const auth = useAuthStore()

const users = ref<any[]>([])
const usersLoading = ref(false)
const saving = ref(false)

const userDialog      = ref(false)
const editUserDialog  = ref(false)
const importUserDialog = ref(false)

const userFormRef     = ref()
const editUserFormRef = ref()

const userForm     = reactive({ email: '', display_name: '', password: '', feishu_open_id: '', is_super_admin: false })
const editUserForm = reactive({ id: 0, email: '', display_name: '', feishu_open_id: '', is_super_admin: false })

const userRules = {
  email:        [{ required: true, message: '请输入邮箱', trigger: 'blur' }, { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  password:     [{ required: true, message: '请输入密码', trigger: 'blur' }, { min: 6, message: '至少6位', trigger: 'blur' }],
}
const editUserRules = {
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
}

// ── 导入用户 ──────────────────────────────────────────────────
const importStep        = ref(0)
const importFileList    = ref<any[]>([])
const importRawRows     = ref<any[]>([])
const importPreviewRows = ref<any[]>([])
const importParseErrors = ref<any[]>([])
const importResult      = ref<any>(null)

async function loadUsers() {
  usersLoading.value = true
  try {
    users.value = await userApi.list() as any[]
  } catch (e: any) {
    ElMessage.error('加载失败：' + (typeof e === 'string' ? e : '请检查是否有管理员权限'))
  } finally {
    usersLoading.value = false
  }
}

onMounted(loadUsers)

function openCreateUser() { userDialog.value = true }
function resetUserForm()  { Object.assign(userForm, { email: '', display_name: '', password: '', feishu_open_id: '', is_super_admin: false }) }

function openEditUser(row: any) {
  Object.assign(editUserForm, {
    id:             row.id,
    email:          row.email,
    display_name:   row.display_name,
    feishu_open_id: row.feishu_open_id || '',
    is_super_admin: row.is_super_admin,
  })
  editUserDialog.value = true
}

function resetEditUserForm() {
  Object.assign(editUserForm, { id: 0, email: '', display_name: '', feishu_open_id: '', is_super_admin: false })
}

async function submitEditUser() {
  const valid = await editUserFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await userApi.update(editUserForm.id, {
      display_name:   editUserForm.display_name,
      feishu_open_id: editUserForm.feishu_open_id || null,
      is_super_admin: editUserForm.is_super_admin,
    })
    ElMessage.success('用户信息已更新')
    editUserDialog.value = false
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '更新失败')
  } finally {
    saving.value = false
  }
}

// 删除用户（软删除 = 停用，后端禁止硬删除）
async function confirmDeleteUser(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认删除用户「${row.display_name}」（${row.email}）？\n\n删除后该用户将无法登录，但历史记录保留。`,
      '删除用户',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
    )
  } catch { return }
  try {
    await userApi.deactivate(row.id)
    ElMessage.success('用户已删除')
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '删除失败')
  }
}

async function deactivateUser(row: any) {
  await ElMessageBox.confirm(`确认停用用户「${row.display_name}」？`, '确认停用', { type: 'warning' })
  try {
    await userApi.deactivate(row.id)
    ElMessage.success('用户已停用')
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '停用失败')
  }
}

async function activateUser(row: any) {
  await ElMessageBox.confirm(`确认重新启用用户「${row.display_name}」？`, '确认启用', { type: 'warning' })
  try {
    await userApi.activate(row.id)
    ElMessage.success('用户已启用')
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '启用失败')
  }
}

function openImportUser() {
  importUserDialog.value = true
}

function resetImportDialog() {
  importStep.value        = 0
  importFileList.value    = []
  importRawRows.value     = []
  importPreviewRows.value = []
  importParseErrors.value = []
  importResult.value      = null
}

function downloadTemplate() {
  const header = 'email,display_name,password,feishu_open_id'
  const rows   = [
    'zhangsan@company.com,张三,Init@123,',
    'lisi@company.com,李四,Init@123,ou_xxxxxxx',
  ]
  const content  = [header, ...rows].join('\n')
  const blob     = new Blob(['\uFEFF' + content], { type: 'text/csv;charset=utf-8;' })
  const url      = URL.createObjectURL(blob)
  const a        = document.createElement('a')
  a.href         = url
  a.download     = 'import_users_template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuote = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuote = !inQuote
    } else if (ch === ',' && !inQuote) {
      result.push(current.trim())
      current = ''
    } else {
      current += ch
    }
  }
  result.push(current.trim())
  return result
}

function onImportFileChange(file: any) {
  importPreviewRows.value = []
  importParseErrors.value = []
  importFileList.value    = [file]

  const reader = new FileReader()
  reader.onload = (e) => {
    const text   = (e.target?.result as string) || ''
    const lines  = text.split(/\r?\n/).filter(l => l.trim())
    const preview: any[] = []
    const errors: any[]  = []

    lines.forEach((line, idx) => {
      if (idx === 0 && /email|邮箱/i.test(line)) return

      const cols = parseCsvLine(line)
      const [email, display_name, password, feishu_open_id] = cols

      if (!email || !display_name || !password) {
        errors.push({ line: idx + 1, raw: line, reason: '缺少必填字段（邮箱/姓名/密码）' })
        return
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        errors.push({ line: idx + 1, raw: line, reason: '邮箱格式不正确' })
        return
      }
      if (password.length < 6) {
        errors.push({ line: idx + 1, raw: line, reason: '密码至少 6 位' })
        return
      }
      preview.push({ email, display_name, password, feishu_open_id: feishu_open_id || '' })
    })

    importPreviewRows.value = preview
    importParseErrors.value = errors
  }
  reader.readAsText(file.raw, 'utf-8')
}

async function submitImport() {
  if (importPreviewRows.value.length === 0) return
  saving.value = true
  try {
    const res = await userApi.importUsers(importPreviewRows.value) as any
    importResult.value = res
    importStep.value   = 2
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '导入失败')
  } finally {
    saving.value = false
  }
}

async function submitUser() {
  const valid = await userFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await userApi.create({ ...userForm })
    ElMessage.success('用户创建成功')
    userDialog.value = false
    await loadUsers()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '创建失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
:deep(.row-deactivated) {
  opacity: 0.45;
}
</style>
