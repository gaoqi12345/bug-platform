<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>项目列表</span>
        <el-button type="primary" size="small" @click="openCreateProject">+ 新建项目</el-button>
      </div>
    </template>

    <el-table :data="allProjects" stripe :style="{ opacity: projectsLoading ? 0.4 : 1, transition: 'opacity 0.2s ease' }">
      <el-table-column prop="id"   label="ID"   width="70" />
      <el-table-column prop="name" label="项目名称" />
      <el-table-column prop="slug" label="Slug" />
      <el-table-column label="所属团队" width="150">
        <template #default="{ row }">
          {{ teams.find(t => t.id === row.team_id)?.name || `Team #${row.team_id}` }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '活跃' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="viewProject(row)">查看</el-button>
          <el-button size="small" type="warning" @click="archiveProject(row)"
            :disabled="row.status !== 'active'">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 新建项目对话框 -->
  <el-dialog v-model="projectDialog" title="新建项目" width="460px" @closed="resetProjectForm">
    <el-form :model="projectForm" :rules="projectRules" ref="projectFormRef" label-width="90px">
      <el-form-item label="所属团队" prop="team_id">
        <el-select v-model="projectForm.team_id" placeholder="请选择团队" style="width:100%">
          <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="projectForm.name" placeholder="如：移动端 App"
          @input="autoSlug" />
      </el-form-item>
      <el-form-item label="Slug" prop="slug">
        <el-input v-model="projectForm.slug" placeholder="如：mobile-app（字母数字-）" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="projectForm.description" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="projectDialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submitProject">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/stores/project'
import { projectApi, teamApi } from '@/api'

const router = useRouter()
const projectStore = useProjectStore()

const allProjects = ref<any[]>([])
const teams = ref<any[]>([])
const projectsLoading = ref(false)
const saving = ref(false)

const projectDialog = ref(false)
const projectFormRef = ref()

const projectForm = reactive({ team_id: null as number|null, name: '', slug: '', description: '' })

const projectRules = {
  team_id: [{ required: true, message: '请选择团队', trigger: 'change' }],
  name:    [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  slug:    [
    { required: true, message: '请输入 slug', trigger: 'blur' },
    { pattern: /^[a-z0-9-]+$/, message: '只允许小写字母、数字和连字符', trigger: 'blur' },
  ],
}

async function loadProjects() {
  projectsLoading.value = true
  try {
    const [p, t] = await Promise.all([
      projectApi.list(true) as any,   // include_archived=true，管理页显示全部
      teamApi.list() as any,
    ])
    allProjects.value = p
    teams.value = t
    // 顶部下拉只同步活跃项目
    projectStore.projects = p.filter((x: any) => x.status === 'active')
  } catch (e: any) {
    ElMessage.error('加载失败：' + (typeof e === 'string' ? e : '请检查是否有管理员权限'))
  } finally {
    projectsLoading.value = false
  }
}

onMounted(loadProjects)

function openCreateProject() { projectDialog.value = true }
function resetProjectForm()  { Object.assign(projectForm, { team_id: null, name: '', slug: '', description: '' }) }

// 查看项目（含已归档）：切换到该项目并跳转到 Bug 列表
function viewProject(row: any) {
  projectStore.setCurrentProject(row.id)
  router.push('/bugs')
}

// 自动将项目名转换为 slug
function autoSlug() {
  projectForm.slug = projectForm.name
    .toLowerCase()
    .replace(/[\u4e00-\u9fa5]/g, '')   // 去中文
    .replace(/[^a-z0-9]+/g, '-')       // 非字母数字转-
    .replace(/^-+|-+$/g, '')           // 去首尾-
}

async function submitProject() {
  const valid = await projectFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const proj = await projectApi.create({ ...projectForm }) as any
    ElMessage.success('项目创建成功')
    projectDialog.value = false
    await loadProjects()
    // 自动切换到新项目
    projectStore.setCurrentProject(proj.id)
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '创建失败')
  } finally {
    saving.value = false
  }
}

async function archiveProject(row: any) {
  await ElMessageBox.confirm(`确认归档项目「${row.name}」？归档后不可创建 Bug。`, '确认归档', { type: 'warning' })
  try {
    await projectApi.archive(row.id)
    ElMessage.success('项目已归档')
    await loadProjects()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '归档失败')
  }
}
</script>
