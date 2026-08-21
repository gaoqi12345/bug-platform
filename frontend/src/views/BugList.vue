<template>
  <div class="buglist-wrap">
    <!-- 筛选栏 -->
    <el-card class="filter-card" :body-style="{ padding: '14px 18px' }">

      <!-- 第一行：常用筛选 + 操作按钮 -->
      <div class="filter-row-main">
        <!-- 状态快捷按钮组 -->
        <div class="status-btn-group">
          <button
            class="status-btn"
            :class="{ active: filters.status_list.length === 0 }"
            @click="setStatus([])"
          >全部</button>
          <button
            v-for="s in STATUS_OPTIONS"
            :key="s.value"
            class="status-btn"
            :class="{ active: filters.status_list.length === 1 && filters.status_list[0] === s.value }"
            @click="setStatus([s.value])"
          >{{ s.label }}</button>
          <!-- 分隔线 -->
          <span class="status-btn-sep" />
          <!-- 指派给我：特殊快捷键，激活条件是 assignee_id = 当前用户 -->
          <button
            class="status-btn status-btn--mine"
            :class="{ active: isAssignedToMe }"
            @click="toggleAssignedToMe"
          >指派给我</button>
        </div>

        <div class="filter-row-right">
          <!-- 关键词搜索（debounce 自动触发） -->
          <el-input
            v-model="filters.keyword"
            placeholder="搜索标题…"
            clearable
            style="width:200px"
            @input="onKeywordInput"
            @clear="search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>

          <!-- 更多筛选展开按钮 -->
          <el-button
            :type="hasAdvancedFilters ? 'primary' : ''"
            :plain="!hasAdvancedFilters"
            :style="hasAdvancedFilters ? { boxShadow: '0 0 0 2px var(--accent-lime)' } : {}"
            @click="showAdvanced = !showAdvanced"
          >
            更多筛选
            <el-icon style="margin-left:4px">
              <ArrowDown v-if="!showAdvanced" /><ArrowUp v-else />
            </el-icon>
            <el-badge v-if="advancedFilterCount > 0" :value="advancedFilterCount" style="margin-left:4px" />
          </el-button>

          <el-button
            type="success"
            :disabled="projectStore.isCurrentProjectArchived || projectStore.currentProjectId === ALL_PROJECTS"
            :title="projectStore.isCurrentProjectArchived
              ? '已归档项目不可新建 Bug'
              : projectStore.currentProjectId === ALL_PROJECTS ? '请先选择具体项目' : ''"
            @click="$router.push('/bugs/create')"
          >+ 新建 Bug</el-button>
        </div>
      </div>

      <!-- 已激活筛选标签行（有高级筛选激活时才显示） -->
      <div v-if="activeFilterTags.length > 0" class="active-tags-row">
        <span class="active-tags-label">已筛选：</span>
        <el-tag
          v-for="tag in activeFilterTags"
          :key="tag.key"
          size="small"
          closable
          type="info"
          style="margin-right:4px;"
          @close="clearFilter(tag.key)"
        >{{ tag.label }}</el-tag>
        <el-button link size="small" class="clear-all-btn" @click="resetFilters">清除全部</el-button>
      </div>

      <!-- 第二行：高级筛选（可折叠） -->
      <transition name="filter-expand">
        <div v-if="showAdvanced" class="filter-row-advanced">
          <el-form inline :model="filters" style="margin:0">
            <el-form-item label="优先级">
              <el-select v-model="filters.priority" clearable placeholder="全部" style="width:100px">
                <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="严重度">
              <el-select v-model="filters.severity" clearable placeholder="全部" style="width:110px">
                <el-option v-for="s in SEVERITY_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="版本">
              <el-select v-model="filters.version_id" clearable placeholder="全部" style="width:120px">
                <el-option v-for="v in versions" :key="v.id" :label="v.name" :value="v.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="创建人">
              <el-select v-model="filters.reporter_id" clearable placeholder="全部" style="width:120px">
                <el-option v-for="m in projectMembers" :key="m.user_id" :label="m.display_name" :value="m.user_id" />
              </el-select>
            </el-form-item>
            <el-form-item label="指派给">
              <el-select v-model="filters.assignee_id" clearable placeholder="全部" style="width:120px">
                <el-option v-for="m in projectMembers" :key="m.user_id" :label="m.display_name" :value="m.user_id" />
              </el-select>
            </el-form-item>
            <el-form-item label="创建时间">
              <el-date-picker
                v-model="filters.date_range"
                type="daterange"
                range-separator="~"
                start-placeholder="开始"
                end-placeholder="结束"
                value-format="YYYY-MM-DD"
                style="width:220px"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="search">查询</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </transition>
    </el-card>

    <!-- Bug 表格 -->
    <el-card>
      <el-table
        :data="bugs"
        stripe
        highlight-current-row
        @row-click="row => $router.push(`/bugs/${row.id}`)"
        @sort-change="onSortChange"
        :style="{ cursor: 'pointer', opacity: loading ? 0.4 : 1, transition: 'opacity 0.2s ease' }"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="project_name" label="项目" width="120" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="280" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="严重度" width="100" sortable="custom" prop="severity">
          <template #default="{ row }">
            <SeverityTag :severity="row.severity" />
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100" sortable="custom" prop="priority">
          <template #default="{ row }">
            <PriorityTag :priority="row.priority" />
          </template>
        </el-table-column>
        <el-table-column prop="assignee_name" label="指派给" width="100">
          <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="reporter_name" label="提交人" width="100" />
        <el-table-column label="创建时间" width="160" sortable="custom" prop="created_at">
          <template #default="{ row }">
            {{ row.created_at?.slice(0, 16).replace('T', ' ') }}
          </template>
        </el-table-column>
      </el-table>

      <div style="display:flex;justify-content:flex-end;margin-top:16px;">
        <el-pagination
          v-model:current-page="page"
          :total="total"
          :page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchBugs"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { useProjectStore, ALL_PROJECTS } from '@/stores/project'
import { useAuthStore } from '@/stores/auth'
import { bugApi, projectApi, versionApi } from '@/api'
import { STATUS_OPTIONS, SEVERITY_OPTIONS, PRIORITY_OPTIONS } from '@/utils/status'
import StatusTag from '@/components/StatusTag.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import PriorityTag from '@/components/PriorityTag.vue'

const route        = useRoute()
const router       = useRouter()
const projectStore = useProjectStore()
const auth         = useAuthStore()

const bugs           = ref<any[]>([])
const total          = ref(0)
const page           = ref(1)
const pageSize       = ref(20)
const loading        = ref(false)
const projectMembers = ref<any[]>([])
const versions       = ref<any[]>([])

// 折叠状态：读 localStorage，首次默认收起
const EXPAND_KEY = 'buglist_advanced_expanded'
const showAdvanced = ref(localStorage.getItem(EXPAND_KEY) === '1')
watch(showAdvanced, v => localStorage.setItem(EXPAND_KEY, v ? '1' : '0'))

interface Filters {
  status_list:   string[]
  priority:      string
  severity:      string
  keyword:       string
  reporter_id:   number | null
  assignee_id:   number | null
  version_id:    number | null
  date_range:    [string, string] | null
  sort_by:       string
  sort_order:    string
}

const EMPTY_FILTERS: Filters = {
  status_list: [],
  priority:    '',
  severity:    '',
  keyword:     '',
  reporter_id: null,
  assignee_id: null,
  version_id:  null,
  date_range:  null,
  sort_by:     'created_at',
  sort_order:  'desc',
}

const filters = reactive<Filters>({ ...EMPTY_FILTERS })

// ── 高级筛选激活状态 ─────────────────────────────────────────
const hasAdvancedFilters = computed(() =>
  !!(filters.priority || filters.severity || filters.version_id ||
     filters.reporter_id || filters.assignee_id || filters.date_range)
)

const advancedFilterCount = computed(() => {
  let n = 0
  if (filters.priority)    n++
  if (filters.severity)    n++
  if (filters.version_id)  n++
  if (filters.reporter_id) n++
  if (filters.assignee_id) n++
  if (filters.date_range)  n++
  return n
})

// 已激活筛选标签（不含状态/关键词/排序，那些已有其他 UI 呈现）
const activeFilterTags = computed(() => {
  const tags: { key: string; label: string }[] = []
  if (filters.priority) {
    const p = PRIORITY_OPTIONS.find((x: any) => x.value === filters.priority)
    tags.push({ key: 'priority', label: `优先级: ${p?.label || filters.priority}` })
  }
  if (filters.severity) {
    const s = SEVERITY_OPTIONS.find((x: any) => x.value === filters.severity)
    tags.push({ key: 'severity', label: `严重度: ${s?.label || filters.severity}` })
  }
  if (filters.version_id) {
    const v = versions.value.find((x: any) => x.id === filters.version_id)
    tags.push({ key: 'version_id', label: `版本: ${v?.name || filters.version_id}` })
  }
  if (filters.reporter_id) {
    const m = projectMembers.value.find((x: any) => x.user_id === filters.reporter_id)
    tags.push({ key: 'reporter_id', label: `创建人: ${m?.display_name || filters.reporter_id}` })
  }
  if (filters.assignee_id) {
    const m = projectMembers.value.find((x: any) => x.user_id === filters.assignee_id)
    tags.push({ key: 'assignee_id', label: `指派给: ${m?.display_name || filters.assignee_id}` })
  }
  if (filters.date_range) {
    tags.push({ key: 'date_range', label: `${filters.date_range[0]} ~ ${filters.date_range[1]}` })
  }
  return tags
})

function clearFilter(key: string) {
  if (key === 'priority')    filters.priority    = ''
  if (key === 'severity')    filters.severity    = ''
  if (key === 'version_id')  filters.version_id  = null
  if (key === 'reporter_id') filters.reporter_id = null
  if (key === 'assignee_id') filters.assignee_id = null
  if (key === 'date_range')  filters.date_range  = null
  search()
}

// 指派给我快捷按钮
const isAssignedToMe = computed(() =>
  !!auth.user?.id && filters.assignee_id === auth.user.id
)
function toggleAssignedToMe() {
  if (isAssignedToMe.value) {
    filters.assignee_id = null
  } else {
    filters.assignee_id = auth.user?.id ?? null
  }
  search()
}

// 表头点击排序
function onSortChange({ prop, order }: { prop: string; order: string | null }) {
  if (!prop || !order) {
    filters.sort_by    = 'created_at'
    filters.sort_order = 'desc'
  } else {
    filters.sort_by    = prop
    filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  }
  page.value = 1
  fetchBugs()
}

// 状态快捷按钮
function setStatus(list: string[]) {
  filters.status_list = list
  search()
}

// 关键词 debounce（400ms）
let keywordTimer: ReturnType<typeof setTimeout> | null = null
function onKeywordInput() {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => search(), 400)
}

// ── URL 同步 ─────────────────────────────────────────────────
function readFromQuery() {
  const q = route.query
  filters.status_list = q.status_list
    ? (Array.isArray(q.status_list) ? q.status_list as string[] : [q.status_list as string])
    : []
  if (!filters.status_list.length && q.status)
    filters.status_list = [q.status as string]
  filters.priority   = (q.priority as string) || ''
  filters.severity   = (q.severity as string) || ''
  filters.keyword    = (q.keyword  as string) || ''
  filters.version_id = q.version_id ? Number(q.version_id) : null
  if (q.assignee_me === '1' && auth.user?.id) {
    filters.assignee_id = auth.user.id
  } else {
    filters.assignee_id = q.assignee_id ? Number(q.assignee_id) : null
  }
  filters.reporter_id = q.reporter_id ? Number(q.reporter_id) : null
  filters.date_range  = (q.date_after && q.date_before)
    ? [q.date_after as string, q.date_before as string] : null
  filters.sort_by    = (q.sort_by    as string) || 'created_at'
  filters.sort_order = (q.sort_order as string) || 'desc'
  page.value     = q.page      ? Number(q.page)      : 1
  pageSize.value = q.page_size ? Number(q.page_size) : 20
  // 有高级筛选条件时自动展开
  if (hasAdvancedFilters.value) showAdvanced.value = true
}

function writeToQuery() {
  const q: Record<string, any> = {}
  if (filters.status_list.length) q.status_list = filters.status_list
  if (filters.priority)           q.priority    = filters.priority
  if (filters.severity)           q.severity    = filters.severity
  if (filters.keyword)            q.keyword     = filters.keyword
  if (filters.reporter_id)        q.reporter_id = String(filters.reporter_id)
  if (filters.assignee_id)        q.assignee_id = String(filters.assignee_id)
  if (filters.version_id)         q.version_id  = String(filters.version_id)
  if (filters.date_range) {
    q.date_after  = filters.date_range[0]
    q.date_before = filters.date_range[1]
  }
  if (filters.sort_by !== 'created_at')  q.sort_by    = filters.sort_by
  if (filters.sort_order !== 'desc')     q.sort_order = filters.sort_order
  if (page.value > 1)                    q.page       = String(page.value)
  if (pageSize.value !== 20)             q.page_size  = String(pageSize.value)
  router.replace({ query: q })
}

// ── 数据获取 ─────────────────────────────────────────────────
async function fetchBugs() {
  const pid = projectStore.currentProjectId
  if (!pid) return
  loading.value = true
  writeToQuery()
  try {
    const params: any = {
      page:       page.value,
      page_size:  pageSize.value,
      sort_by:    filters.sort_by,
      sort_order: filters.sort_order,
    }
    // 「全部项目」模式不传 project_id，后端按用户所属项目返回
    if (pid !== ALL_PROJECTS) params.project_id = pid
    if (filters.status_list.length) params.status_list = filters.status_list
    if (filters.priority)    params.priority    = filters.priority
    if (filters.severity)    params.severity    = filters.severity
    if (filters.keyword)     params.keyword     = filters.keyword
    if (filters.reporter_id) params.reporter_id = filters.reporter_id
    if (filters.assignee_id) params.assignee_id = filters.assignee_id
    if (filters.version_id)  params.version_id  = filters.version_id
    if (filters.date_range) {
      params.created_after  = filters.date_range[0]
      params.created_before = filters.date_range[1]
    }
    const res = await bugApi.list(params) as any
    bugs.value  = res.items
    total.value = res.total
  } catch {}
  loading.value = false
}

function search() {
  page.value = 1
  fetchBugs()
}

function resetFilters() {
  Object.assign(filters, { ...EMPTY_FILTERS })
  page.value     = 1
  pageSize.value = 20
  fetchBugs()
}

function onSizeChange(size: number) {
  pageSize.value = size
  page.value     = 1
  fetchBugs()
}

async function loadProjectData() {
  const pid = projectStore.currentProjectId
  // 「全部项目」模式没有单一项目的成员/版本数据，跳过（筛选下拉留空）
  if (!pid || pid === ALL_PROJECTS) return
  try {
    const [members, vlist] = await Promise.all([
      projectApi.listMembers(pid) as any[],
      versionApi.list(pid)        as any[],
    ])
    projectMembers.value = members
    versions.value       = vlist
  } catch {}
}

onMounted(async () => {
  readFromQuery()
  await loadProjectData()
  await fetchBugs()
})

watch(() => projectStore.currentProjectId, async () => {
  Object.assign(filters, { ...EMPTY_FILTERS })
  page.value = 1
  await loadProjectData()
  await fetchBugs()
})
</script>

<style scoped>
/* ── 筛选卡片 ─────────────────────────── */
.filter-card {
  margin-bottom: 16px;
}

/* ── 主筛选行 ─────────────────────────── */
.filter-row-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

/* ── 右侧操作区 ───────────────────────── */
.filter-row-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ── 状态快捷按钮组 ────────────────────── */
.status-btn-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.status-btn {
  background: var(--bg-surface-2);
  border: 1px solid var(--border-subtle);
  border-radius: 9999px;
  padding: 5px 14px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font-sans);
  outline: none;
  white-space: nowrap;
  line-height: 1.5;
}

.status-btn:focus {
  outline: none;
}

.status-btn.active {
  background: var(--accent-lime);
  color: var(--text-inverse);
  border-color: var(--accent-lime);
  font-weight: 700;
}

.status-btn:hover:not(.active) {
  background: var(--bg-surface-3);
  color: var(--text-primary);
}

/* 指派给我：虚线边框，未激活时区分样式 */
.status-btn--mine {
  border-style: dashed;
}

.status-btn--mine.active {
  background: var(--accent-lime);
  color: var(--text-inverse);
  border-color: var(--accent-lime);
  border-style: solid;
  font-weight: 700;
}

/* 分隔线 */
.status-btn-sep {
  display: inline-block;
  width: 1px;
  height: 18px;
  background: var(--border-subtle);
  flex-shrink: 0;
}

/* ── 已激活标签行 ───────────────────────── */
.active-tags-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border-subtle);
}

.active-tags-label {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.clear-all-btn {
  color: var(--text-muted) !important;
  font-size: 12px;
}

/* ── 高级筛选展开区 ─────────────────────── */
.filter-row-advanced {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
}

/* ── 折叠动画（max-height approach） ────── */
.filter-expand-enter-active,
.filter-expand-leave-active {
  transition: all 0.22s ease;
  overflow: hidden;
}

.filter-expand-enter-from,
.filter-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.filter-expand-enter-to,
.filter-expand-leave-from {
  opacity: 1;
  max-height: 200px;
}
</style>
