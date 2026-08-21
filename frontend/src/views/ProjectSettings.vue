<template>
  <div>
    <!-- 「全部项目」模式提示 -->
    <el-alert
      v-if="projectStore.currentProjectId === ALL_PROJECTS"
      type="info"
      :closable="false"
      show-icon
      title="「全部项目」模式下不支持项目设置，请在上方选择具体项目"
      style="margin-bottom:16px"
    />
    <el-tabs v-model="activeTab">
      <!-- 版本管理 -->
      <el-tab-pane label="版本管理" name="versions">
        <el-card>
          <template #header>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="card-header-title">版本列表</span>
              <el-button type="primary" size="small" @click="showCreateVersion = true">+ 新建版本</el-button>
            </div>
          </template>
          <el-table :data="versions" stripe>
            <el-table-column prop="name" label="版本名" min-width="140" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="VERSION_STATUS_TYPE[row.status]">
                  {{ VERSION_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="120">
              <template #default="{ row }">{{ row.start_date?.slice(0,10) || '—' }}</template>
            </el-table-column>
            <el-table-column label="结束时间" width="120">
              <template #default="{ row }">{{ row.end_date?.slice(0,10) || '—' }}</template>
            </el-table-column>
            <el-table-column prop="released_at" label="发布时间" width="120">
              <template #default="{ row }">{{ row.released_at?.slice(0,10) || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="openEditVersion(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 项目成员 -->
      <el-tab-pane label="项目成员" name="members">
        <el-card>
          <template #header>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="card-header-title">成员列表</span>
              <el-button type="primary" size="small" @click="showAddMember = true">+ 添加成员</el-button>
            </div>
          </template>
          <el-table :data="members" stripe>
            <el-table-column prop="display_name" label="姓名" />
            <el-table-column label="有效角色" width="110">
              <template #default="{ row }">
                <el-tag :type="ROLE_TYPE[row.effective_role]">
                  {{ ROLE_LABEL[row.effective_role] || row.effective_role }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="120">
              <template #default="{ row }">
                <el-tag type="info" size="small">{{ SOURCE_LABEL[row.role_source] || row.role_source }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" plain @click="openEditMember(row)">改角色</el-button>
                <el-button
                  v-if="row.role_source !== 'team_inherited'"
                  size="small" type="danger" plain
                  @click="removeMember(row)"
                >移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top:12px; font-size:12px; color:var(--text-muted);">
            · 团队继承：角色来自团队设置，可覆盖但不可直接移除（需在系统管理中调整团队成员）<br/>
            · 项目覆盖：对团队成员单独设置了角色，可移除恢复为团队默认角色<br/>
            · 直接成员：不在团队中、直接加入本项目的成员，可移除
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建版本对话框 -->
    <el-dialog v-model="showCreateVersion" title="新建版本" width="460px" @closed="resetVersionForm">
      <el-form :model="versionForm" label-width="90px">
        <el-form-item label="版本名" required>
          <el-input v-model="versionForm.name" placeholder="如：v1.0、sprint-3" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="versionForm.start_date"
            type="date"
            placeholder="选择开始日期"
            style="width:100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="versionForm.end_date"
            type="date"
            placeholder="选择结束日期"
            style="width:100%"
            value-format="YYYY-MM-DD"
            :disabled-date="(d: Date) => versionForm.start_date ? d < new Date(versionForm.start_date) : false"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="versionForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateVersion = false">取消</el-button>
        <el-button type="primary" :loading="versionLoading" @click="createVersion">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑版本对话框 -->
    <el-dialog v-model="showEditVersion" title="编辑版本" width="460px" @closed="resetEditVersionForm">
      <el-form :model="editVersionForm" label-width="90px">
        <el-form-item label="版本名" required>
          <el-input v-model="editVersionForm.name" placeholder="如：v1.0、sprint-3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editVersionForm.status" style="width:100%">
            <el-option
              v-for="(label, key) in VERSION_STATUS_LABEL"
              :key="key"
              :label="label"
              :value="key"
              :disabled="!isStatusSelectable(key)"
            />
          </el-select>
          <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
            状态只能向前推进，不可回退
          </div>
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="editVersionForm.start_date"
            type="date"
            placeholder="选择开始日期"
            style="width:100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="editVersionForm.end_date"
            type="date"
            placeholder="选择结束日期"
            style="width:100%"
            value-format="YYYY-MM-DD"
            :disabled-date="(d: Date) => editVersionForm.start_date ? d < new Date(editVersionForm.start_date) : false"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editVersionForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
          <el-button type="danger" plain :loading="versionLoading" @click="deleteVersion">删除版本</el-button>
          <div style="display:flex; gap:8px;">
            <el-button @click="showEditVersion = false">取消</el-button>
            <el-button type="primary" :loading="versionLoading" @click="submitEditVersion">保存</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 添加成员对话框 -->
    <el-dialog v-model="showAddMember" title="添加项目成员" width="420px" @closed="resetMemberForm">
      <div style="color:var(--text-muted); font-size:12px; margin-bottom:16px;">
        将不在当前项目中的用户加入本项目，或为已有成员设置项目专属角色。
      </div>
      <el-form :model="memberForm" label-width="80px">
        <el-form-item label="用户">
          <el-select v-model="memberForm.user_id" filterable placeholder="搜索用户" style="width:100%">
            <el-option
              v-for="u in nonTeamUsers"
              :key="u.id"
              :label="`${u.display_name}（${u.email}）`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目角色">
          <el-select v-model="memberForm.role" style="width:100%">
            <el-option
              v-for="r in rbacStore.roles"
              :key="r.name"
              :label="r.label"
              :value="r.name"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMember = false">取消</el-button>
        <el-button type="primary" :loading="memberLoading" @click="addMember">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑成员角色对话框 -->
    <el-dialog v-model="showEditMember" title="修改项目角色" width="380px" @closed="resetEditMemberForm">
      <div style="margin-bottom:12px; color:var(--text-secondary); font-size:14px;">
        成员：<strong>{{ editMemberForm.display_name }}</strong>
        <el-tag type="info" size="small" style="margin-left:8px;">
          {{ SOURCE_LABEL[editMemberForm.role_source] }}
        </el-tag>
      </div>
      <el-form :model="editMemberForm" label-width="80px">
        <el-form-item label="项目角色">
          <el-select v-model="editMemberForm.role" style="width:100%">
            <el-option
              v-for="r in rbacStore.roles"
              :key="r.name"
              :label="r.label"
              :value="r.name"
            />
          </el-select>
        </el-form-item>
        <div v-if="editMemberForm.role_source === 'team_inherited'" style="font-size:12px; color:var(--color-warning); margin-top:4px;">
          保存后将在项目层覆盖团队角色。如需恢复团队默认角色，可点击成员列表中的「移除」按钮。
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showEditMember = false">取消</el-button>
        <el-button type="primary" :loading="memberLoading" @click="submitEditMember">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore, ALL_PROJECTS } from '@/stores/project'
import { useRbacStore } from '@/stores/rbac'
import { versionApi, projectApi, userApi } from '@/api'

const projectStore = useProjectStore()
const rbacStore = useRbacStore()
const activeTab = ref('versions')
const versions  = ref<any[]>([])
const members   = ref<any[]>([])
const allUsers  = ref<any[]>([])

const showCreateVersion = ref(false)
const showEditVersion   = ref(false)
const showAddMember     = ref(false)
const showEditMember    = ref(false)
const versionLoading    = ref(false)
const memberLoading     = ref(false)

const versionForm     = reactive({ name: '', description: '', start_date: '', end_date: '' })
const editVersionForm = reactive({ id: 0, name: '', description: '', start_date: '', end_date: '', status: '', _origStatus: '' })
const memberForm      = reactive({ user_id: null as number | null, role: 'developer' })
const editMemberForm  = reactive({ user_id: 0, display_name: '', role: '', role_source: '' })

// ── 静态映射 ──────────────────────────────────────────────────
const VERSION_STATUS_ORDER = ['planning', 'active', 'released', 'archived']
const VERSION_STATUS_LABEL: Record<string, string> = {
  planning: '规划中', active: '进行中', released: '已发布', archived: '已归档',
}
const VERSION_STATUS_TYPE: Record<string, string> = {
  planning: 'info', active: 'primary', released: 'success', archived: 'warning',
}
// 角色标签：优先从 rbac store 动态读取（支持自定义角色），
// store 未加载完成时回退到内置角色的静态映射
const STATIC_ROLE_LABEL: Record<string, string> = {
  pm: 'PM', developer: '开发', tester: '测试', viewer: '只读',
}
const ROLE_LABEL = computed<Record<string, string>>(() => {
  if (!rbacStore.loaded || rbacStore.roles.length === 0) return STATIC_ROLE_LABEL
  const map: Record<string, string> = {}
  for (const r of rbacStore.roles) map[r.name] = r.label
  return map
})
const STATIC_ROLE_TYPE: Record<string, string> = {
  pm: 'danger', developer: 'primary', tester: 'success', viewer: 'info',
}
const ROLE_TYPE = computed<Record<string, string>>(() => STATIC_ROLE_TYPE)
const SOURCE_LABEL: Record<string, string> = {
  team_inherited: '团队继承', project_override: '项目覆盖', direct_member: '直接成员',
}

// ── 计算属性：非团队成员 ─────────────────────────────────────
// 不在当前项目成员列表里的用户（用于直接添加）
const nonTeamUsers = computed(() => {
  const existIds = new Set(members.value.map((m: any) => m.user_id))
  return allUsers.value.filter((u: any) => !existIds.has(u.id))
})

// ── 版本表单 reset ────────────────────────────────────────────
function resetVersionForm() {
  Object.assign(versionForm, { name: '', description: '', start_date: '', end_date: '' })
}
function resetEditVersionForm() {
  Object.assign(editVersionForm, { id: 0, name: '', description: '', start_date: '', end_date: '', status: '', _origStatus: '' })
}

// ── 成员表单 reset ────────────────────────────────────────────
function resetMemberForm() {
  memberForm.user_id = null
  memberForm.role = 'developer'
}
function resetEditMemberForm() {
  Object.assign(editMemberForm, { user_id: 0, display_name: '', role: '', role_source: '' })
}

// ── 版本状态：只能向前推进 ────────────────────────────────────
function isStatusSelectable(key: string) {
  const currentIdx = VERSION_STATUS_ORDER.indexOf(editVersionForm.status)
  const targetIdx  = VERSION_STATUS_ORDER.indexOf(key)
  return targetIdx >= currentIdx
}

function openEditVersion(row: any) {
  Object.assign(editVersionForm, {
    id:          row.id,
    name:        row.name,
    description: row.description || '',
    start_date:  row.start_date ? row.start_date.slice(0, 10) : '',
    end_date:    row.end_date   ? row.end_date.slice(0, 10)   : '',
    status:      row.status,
    _origStatus: row.status,
  })
  showEditVersion.value = true
}

function openEditMember(row: any) {
  Object.assign(editMemberForm, {
    user_id:     row.user_id,
    display_name: row.display_name,
    role:        row.effective_role,
    role_source: row.role_source,
  })
  showEditMember.value = true
}

// ── 数据加载 ──────────────────────────────────────────────────
async function loadData() {
  const pid = projectStore.currentProjectId
  if (pid <= 0) return
  try {
    const [v, m] = await Promise.all([
      versionApi.list(pid) as any,
      projectApi.listMembers(pid) as any,
    ])
    versions.value = v
    members.value  = m
  } catch {}
}

onMounted(async () => {
  await loadData()
  try { allUsers.value = await userApi.list() as any[] } catch {}
  if (!rbacStore.loaded) await rbacStore.load()
})
watch(() => projectStore.currentProjectId, loadData)

// ── 版本 CRUD ─────────────────────────────────────────────────
async function createVersion() {
  const pid = projectStore.currentProjectId
  if (pid <= 0 || !versionForm.name) { ElMessage.warning('请填写版本名'); return }
  versionLoading.value = true
  try {
    await versionApi.create(pid, {
      ...versionForm,
      // 未填日期时传 null（与更新路径一致），避免空字符串触发后端 422
      start_date: versionForm.start_date || null,
      end_date:   versionForm.end_date   || null,
    })
    ElMessage.success('版本创建成功')
    showCreateVersion.value = false
    resetVersionForm()
    await loadData()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '创建失败')
  } finally {
    versionLoading.value = false
  }
}

async function submitEditVersion() {
  const pid = projectStore.currentProjectId
  if (pid <= 0 || !editVersionForm.name) { ElMessage.warning('请填写版本名'); return }
  versionLoading.value = true
  try {
    const payload: any = {
      name:        editVersionForm.name,
      description: editVersionForm.description,
      start_date:  editVersionForm.start_date || null,
      end_date:    editVersionForm.end_date   || null,
    }
    if (editVersionForm.status !== editVersionForm._origStatus) {
      payload.status = editVersionForm.status
    }
    await versionApi.update(pid, editVersionForm.id, payload)
    ElMessage.success('版本已更新')
    showEditVersion.value = false
    await loadData()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '更新失败')
  } finally {
    versionLoading.value = false
  }
}

async function deleteVersion() {
  try {
    await ElMessageBox.confirm(
      `确认删除版本「${editVersionForm.name}」？此操作不可恢复。`,
      '删除版本',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
    )
  } catch { return }
  const pid = projectStore.currentProjectId
  if (pid <= 0) return
  versionLoading.value = true
  try {
    await versionApi.delete(pid, editVersionForm.id)
    ElMessage.success('版本已删除')
    showEditVersion.value = false
    await loadData()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '删除失败')
  } finally {
    versionLoading.value = false
  }
}

// ── 成员管理 ──────────────────────────────────────────────────
async function addMember() {
  const pid = projectStore.currentProjectId
  if (pid <= 0 || !memberForm.user_id) { ElMessage.warning('请选择用户'); return }
  memberLoading.value = true
  try {
    await projectApi.overrideMember(pid, { ...memberForm })
    ElMessage.success('成员已添加')
    showAddMember.value = false
    resetMemberForm()
    await loadData()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '操作失败')
  } finally {
    memberLoading.value = false
  }
}

async function submitEditMember() {
  const pid = projectStore.currentProjectId
  if (pid <= 0) return
  memberLoading.value = true
  try {
    await projectApi.overrideMember(pid, { user_id: editMemberForm.user_id, role: editMemberForm.role })
    ElMessage.success('角色已更新')
    showEditMember.value = false
    await loadData()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '操作失败')
  } finally {
    memberLoading.value = false
  }
}

async function removeMember(row: any) {
  const label = row.role_source === 'direct_member'
    ? `确认将「${row.display_name}」从本项目移除？`
    : `确认移除「${row.display_name}」的项目角色覆盖？移除后将恢复为团队默认角色。`
  try {
    await ElMessageBox.confirm(label, '确认操作', {
      type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消',
    })
  } catch { return }
  const pid = projectStore.currentProjectId
  if (pid <= 0) return
  try {
    await projectApi.removeMember(pid, row.user_id)
    ElMessage.success(row.role_source === 'direct_member' ? '已移除成员' : '已恢复团队默认角色')
    await loadData()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '操作失败')
  }
}
</script>

<style scoped>
.card-header-title {
  color: var(--text-primary);
  font-weight: 500;
}
</style>
