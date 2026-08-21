<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>团队列表</span>
        <el-button type="primary" size="small" @click="openCreateTeam">+ 新建团队</el-button>
      </div>
    </template>

    <el-table :data="teams" stripe :style="{ opacity: teamsLoading ? 0.4 : 1, transition: 'opacity 0.2s ease' }">
      <el-table-column prop="id"   label="ID"   width="60" />
      <el-table-column prop="name" label="团队名称" width="160" />
      <el-table-column prop="slug" label="Slug" width="160" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="openEditTeam(row)">编辑</el-button>
          <el-button size="small" @click="openMembers(row)">成员管理</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 成员管理抽屉 -->
  <el-drawer v-model="memberDrawer" :title="`成员管理 — ${currentTeam?.name}`" size="500px">
    <div style="padding:0 16px;">
      <el-button type="primary" size="small" style="margin-bottom:16px;" @click="openAddMember">
        + 添加成员
      </el-button>
      <el-table :data="members" stripe>
        <el-table-column prop="display_name" label="姓名" />
        <el-table-column prop="email" label="邮箱" show-overflow-tooltip />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" @change="(v:string) => changeRole(row, v)">
              <el-option label="管理员" value="admin" />
              <el-option label="成员"   value="member" />
              <el-option label="只读"   value="viewer" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="removeMember(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-drawer>

  <!-- 新建团队对话框 -->
  <el-dialog v-model="teamDialog" title="新建团队" width="400px" @closed="resetTeamForm">
    <el-form :model="teamForm" :rules="teamRules" ref="teamFormRef" label-width="80px">
      <el-form-item label="团队名称" prop="name">
        <el-input v-model="teamForm.name" placeholder="如：后端团队" />
      </el-form-item>
      <el-form-item label="Slug" prop="slug">
        <el-input v-model="teamForm.slug" placeholder="如：backend-team（字母数字-）" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="teamForm.description" type="textarea" :rows="2" placeholder="团队简介（可选）" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="teamDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submitTeam">创建</el-button>
    </template>
  </el-dialog>

  <!-- 编辑团队对话框 -->
  <el-dialog v-model="editTeamDialog" title="编辑团队" width="400px" @closed="resetEditTeamForm">
    <el-form :model="editTeamForm" :rules="editTeamRules" ref="editTeamFormRef" label-width="80px">
      <el-form-item label="团队名称" prop="name">
        <el-input v-model="editTeamForm.name" placeholder="如：后端团队" />
      </el-form-item>
      <el-form-item label="Slug">
        <el-input v-model="editTeamForm.slug" disabled />
        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Slug 创建后不可修改</div>
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="editTeamForm.description" type="textarea" :rows="3" placeholder="团队简介（可选）" />
      </el-form-item>
    </el-form>
    <template #footer>
      <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
        <el-button type="danger" plain :loading="saving" @click="deleteTeamFromEdit">删除团队</el-button>
        <div style="display:flex; gap:8px;">
          <el-button @click="editTeamDialog = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="submitEditTeam">保存</el-button>
        </div>
      </div>
    </template>
  </el-dialog>

  <!-- 添加团队成员对话框（多选） -->
  <el-dialog v-model="addMemberDialog" title="添加成员" width="480px" @closed="resetMemberForm">
    <el-form :model="memberForm" label-width="80px">
      <el-form-item label="选择用户">
        <el-select
          v-model="memberForm.user_ids"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          placeholder="搜索并选择用户（可多选）"
          style="width:100%"
        >
          <el-option
            v-for="u in availableUsers"
            :key="u.id"
            :label="`${u.display_name} (${u.email})`"
            :value="u.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="统一角色">
        <el-select v-model="memberForm.role" style="width:100%">
          <el-option label="管理员 (admin)" value="admin" />
          <el-option label="成员 (member)"  value="member" />
          <el-option label="只读 (viewer)"  value="viewer" />
        </el-select>
      </el-form-item>
      <div v-if="memberForm.user_ids.length > 0"
        style="font-size:12px;color:var(--text-muted);margin-left:80px;margin-top:-6px;">
        已选 {{ memberForm.user_ids.length }} 位用户，将全部设为「{{ TEAM_ROLE_LABELS[memberForm.role] }}」
      </div>
    </el-form>
    <template #footer>
      <el-button @click="addMemberDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving"
        :disabled="memberForm.user_ids.length === 0"
        @click="submitAddMember">
        添加 {{ memberForm.user_ids.length > 0 ? memberForm.user_ids.length + ' 人' : '' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { teamApi, userApi } from '@/api'

const teams = ref<any[]>([])
const members = ref<any[]>([])
const users = ref<any[]>([])
const teamsLoading = ref(false)
const saving = ref(false)

const currentTeam = ref<any>(null)
const memberDrawer = ref(false)

const teamDialog      = ref(false)
const editTeamDialog  = ref(false)
const addMemberDialog = ref(false)

const teamFormRef     = ref()
const editTeamFormRef = ref()

const teamForm     = reactive({ name: '', slug: '', description: '' })
const editTeamForm = reactive({ id: 0, name: '', slug: '', description: '' })
const memberForm   = reactive({ user_ids: [] as number[], role: 'member' })

const teamRules = {
  name: [{ required: true, message: '请输入团队名称', trigger: 'blur' }],
  slug: [
    { required: true, message: '请输入 slug', trigger: 'blur' },
    { pattern: /^[a-z0-9-]+$/, message: '只允许小写字母、数字和连字符', trigger: 'blur' },
  ],
}
const editTeamRules = {
  name: [{ required: true, message: '请输入团队名称', trigger: 'blur' }],
}

const TEAM_ROLE_LABELS: Record<string, string> = { admin: '管理员', member: '成员', viewer: '只读' }

// 可添加的用户（排除已在团队中的）
const availableUsers = computed(() => {
  const existIds = new Set(members.value.map((m: any) => m.user_id))
  return users.value.filter((u: any) => !existIds.has(u.id))
})

async function loadTeams() {
  teamsLoading.value = true
  try {
    const [t, u] = await Promise.all([
      teamApi.list() as any,
      userApi.list() as any,
    ])
    teams.value = t
    users.value = u
  } catch (e: any) {
    ElMessage.error('加载失败：' + (typeof e === 'string' ? e : '请检查是否有管理员权限'))
  } finally {
    teamsLoading.value = false
  }
}

onMounted(loadTeams)

function openCreateTeam() { teamDialog.value = true }
function resetTeamForm()  { Object.assign(teamForm, { name: '', slug: '', description: '' }) }

function openEditTeam(row: any) {
  Object.assign(editTeamForm, { id: row.id, name: row.name, slug: row.slug, description: row.description || '' })
  editTeamDialog.value = true
}
function resetEditTeamForm() { Object.assign(editTeamForm, { id: 0, name: '', slug: '', description: '' }) }

async function submitTeam() {
  const valid = await teamFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await teamApi.create({ ...teamForm })
    ElMessage.success('团队创建成功')
    teamDialog.value = false
    await loadTeams()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '创建失败')
  } finally {
    saving.value = false
  }
}

async function submitEditTeam() {
  const valid = await editTeamFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await teamApi.update(editTeamForm.id, { name: editTeamForm.name, description: editTeamForm.description })
    ElMessage.success('团队信息已更新')
    editTeamDialog.value = false
    await loadTeams()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '更新失败')
  } finally {
    saving.value = false
  }
}

async function deleteTeamFromEdit() {
  try {
    await ElMessageBox.confirm(
      `确认删除团队「${editTeamForm.name}」？删除后该团队下的所有成员关系将一并清除，此操作不可恢复。`,
      '删除团队',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await teamApi.delete(editTeamForm.id)
    ElMessage.success('团队已删除')
    editTeamDialog.value = false
    await loadTeams()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '删除失败')
  } finally {
    saving.value = false
  }
}

async function openMembers(team: any) {
  currentTeam.value = team
  memberDrawer.value = true
  try {
    members.value = await teamApi.listMembers(team.id) as any[]
  } catch {}
}

function openAddMember() { addMemberDialog.value = true }
function resetMemberForm() { memberForm.user_ids = []; memberForm.role = 'member' }

async function submitAddMember() {
  if (memberForm.user_ids.length === 0) { ElMessage.warning('请选择用户'); return }
  saving.value = true
  try {
    const payload = memberForm.user_ids.map(uid => ({ user_id: uid, role: memberForm.role }))
    const res = await teamApi.addMembers(currentTeam.value.id, payload) as any
    const msg = res.skipped > 0
      ? `成功添加 ${res.added} 人，${res.skipped} 人已在团队中`
      : `成功添加 ${res.added} 人`
    ElMessage.success(msg)
    addMemberDialog.value = false
    resetMemberForm()
    members.value = await teamApi.listMembers(currentTeam.value.id) as any[]
    users.value = await userApi.list() as any[]
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '添加失败')
  } finally {
    saving.value = false
  }
}

async function changeRole(row: any, newRole: string) {
  try {
    await teamApi.updateMember(currentTeam.value.id, row.user_id, { role: newRole })
    row.role = newRole
    ElMessage.success('角色已更新')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '更新失败')
  }
}

async function removeMember(row: any) {
  await ElMessageBox.confirm(`确认将「${row.display_name}」从团队移除？`, '确认移除', { type: 'warning' })
  try {
    await teamApi.removeMember(currentTeam.value.id, row.user_id)
    ElMessage.success('已移除')
    members.value = await teamApi.listMembers(currentTeam.value.id) as any[]
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '移除失败')
  }
}
</script>
