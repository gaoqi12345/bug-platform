<template>
  <div>
    <!-- 筛选栏 -->
    <el-card class="filter-card">
      <el-form inline>
        <el-form-item label="优先级">
          <el-select v-model="filters.priority" clearable placeholder="全部" style="width:100px">
            <el-option v-for="p in CASE_PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="最近结果">
          <el-select v-model="filters.last_result" clearable placeholder="全部" style="width:110px">
            <el-option label="通过" value="passed" />
            <el-option label="失败" value="failed" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="跳过" value="skipped" />
            <el-option label="未执行" value="not_run" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索标题" style="width:160px"
            clearable @keyup.enter="fetchCases" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchCases">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
        <el-form-item style="float:right">
          <el-button type="success" :disabled="isAllProjects"
            :title="isAllProjects ? '请先选择具体项目' : ''" @click="openCreate">+ 新建用例</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 「全部项目」模式提示 -->
    <el-alert
      v-if="isAllProjects"
      type="info"
      :closable="false"
      show-icon
      title="「全部项目」模式下可浏览所有项目的用例，新建/执行/编辑请先选择具体项目"
      style="margin-bottom:16px"
    />

    <!-- 用例列表 -->
    <el-card>
      <el-table :data="cases" stripe :row-style="{ cursor: 'pointer' }"
        :style="{ opacity: loading ? 0.4 : 1, transition: 'opacity 0.2s ease' }"
        @row-click="goDetail">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="project_name" label="项目" width="120" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :style="CASE_PRIORITY_STYLE[row.priority] || CASE_PRIORITY_STYLE['P2']" size="small">
              {{ row.priority?.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近结果" width="130">
          <template #default="{ row }">
            <span v-if="row.last_run">
              <el-tag :type="RUN_RESULT_TYPE[row.last_run.result]" size="small">
                {{ RUN_RESULT_LABEL[row.last_run.result] }}
              </el-tag>
              <span style="font-size:11px; color:var(--text-muted); margin-left:4px;">
                {{ row.last_run.version_name ? `(${row.last_run.version_name})` : '' }}
              </span>
            </span>
            <el-tag v-else type="info" size="small">未执行</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="creator_name" label="创建人" width="90" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <div style="display:flex; gap:4px;">
              <el-button size="small" type="primary" plain :disabled="isAllProjects"
                :title="isAllProjects ? '请先选择具体项目' : ''" @click.stop="openRun(row)">执行</el-button>
              <el-button size="small" type="warning" plain :disabled="isAllProjects"
                :title="isAllProjects ? '请先选择具体项目' : ''" @click.stop="openEdit(row)">编辑</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex; justify-content:flex-end; margin-top:16px;">
        <el-pagination
          v-model:current-page="page"
          :total="total"
          :page-size="20"
          layout="total, prev, pager, next"
          @current-change="fetchCases"
        />
      </div>
    </el-card>

    <!-- 新建/编辑用例对话框 -->
    <CaseFormDialog
      v-model="showCaseDialog"
      :editing-case="editingCase"
      :project-id="projectStore.currentProjectId"
      @saved="fetchCases"
    />

    <!-- 执行弹窗 -->
    <RunDialog
      v-model="showRunDialog"
      :running-case="runningCase"
      :project-id="projectStore.currentProjectId"
      :versions="versions"
      :project-bugs="projectBugs"
      @submitted="onRunSubmitted"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore, ALL_PROJECTS } from '@/stores/project'
import { testCaseApi, versionApi, bugApi } from '@/api'
import CaseFormDialog from '@/components/CaseFormDialog.vue'
import RunDialog from '@/components/RunDialog.vue'
import { CASE_PRIORITY_OPTIONS, CASE_PRIORITY_STYLE, RUN_RESULT_LABEL, RUN_RESULT_TYPE } from '@/utils/caseConstants'

const router = useRouter()
const projectStore = useProjectStore()

// 「全部项目」模式：列表可跨项目浏览，但新建/执行/编辑需具体项目
const isAllProjects = computed(() => projectStore.currentProjectId === ALL_PROJECTS)

// ── 数据 ──────────────────────────────────────────────────────
const cases     = ref<any[]>([])
const total     = ref(0)
const page      = ref(1)
const loading   = ref(false)
const versions  = ref<any[]>([])
const projectBugs = ref<any[]>([])

// 对话框状态
const showCaseDialog   = ref(false)
const showRunDialog    = ref(false)
const editingCase      = ref<any>(null)
const runningCase      = ref<any>(null)

// 筛选
const filters = reactive({ priority: '', last_result: '', keyword: '' })

// ── 加载数据 ──────────────────────────────────────────────────
async function fetchCases() {
  const pid = projectStore.currentProjectId
  if (!pid) return
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: 20 }
    if (filters.priority)    params.priority = filters.priority
    if (filters.last_result) params.last_result = filters.last_result
    if (filters.keyword)     params.keyword = filters.keyword
    // 「全部项目」模式走跨项目接口（后端按用户所属项目过滤）
    const res = pid === ALL_PROJECTS
      ? await testCaseApi.listAll(params) as any
      : await testCaseApi.list(pid, params) as any
    cases.value = res.items
    total.value = res.total
  } catch {}
  loading.value = false
}

async function loadVersionsAndBugs() {
  const pid = projectStore.currentProjectId
  if (!pid || pid === ALL_PROJECTS) return
  try {
    const [vlist, bugs] = await Promise.all([
      versionApi.list(pid) as any[],
      bugApi.list({ project_id: pid, page: 1, page_size: 100 }) as any,
    ])
    versions.value = vlist
    projectBugs.value = bugs.items ?? []
  } catch {}
}

function resetFilters() {
  Object.assign(filters, { priority: '', last_result: '', keyword: '' })
  page.value = 1
  fetchCases()
}

onMounted(async () => {
  await fetchCases()
  await loadVersionsAndBugs()
})
watch(() => projectStore.currentProjectId, async () => {
  page.value = 1
  await fetchCases()
  await loadVersionsAndBugs()
})

// ── 对话框协调 ────────────────────────────────────────────────
function openCreate() {
  editingCase.value = null
  showCaseDialog.value = true
}

function openEdit(row: any) {
  editingCase.value = row
  showCaseDialog.value = true
}

function openRun(row: any) {
  runningCase.value = row
  showRunDialog.value = true
}

// 点击行 → 进入用例详情页（跨项目模式下同样可用，详情页自带项目上下文）
function goDetail(row: any) {
  router.push(`/testcases/${row.id}`)
}

// 执行提交成功：刷新列表
async function onRunSubmitted(caseId: number) {
  await fetchCases()
}
</script>

<style scoped>
.filter-card {
  margin-bottom: 16px;
}
</style>
