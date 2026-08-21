<template>
  <div class="dashboard">
    <!-- 顶部欢迎栏 -->
    <div class="welcome-bar">
      <div class="welcome-text">
        <span class="greeting">{{ greeting }}，{{ auth.user?.display_name || auth.user?.email }}</span>
        <span class="date-info">{{ todayStr }}</span>
      </div>
      <el-button type="primary" @click="$router.push('/bugs/create')">
        <el-icon style="margin-right:4px;"><Plus /></el-icon>新建 Bug
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom:20px;">
      <el-col :span="6">
        <StatCard tone="blue" :icon="User" :value="myStats.assigned_to_me" label="指派给我" @click="goToBugs('assigned')" />
      </el-col>
      <el-col :span="6">
        <StatCard tone="orange" :icon="EditPen" :value="myStats.reported_by_me" label="我提交的（未关闭）" @click="goToBugs('reported')" />
      </el-col>
      <el-col :span="6">
        <StatCard tone="green" :icon="Check" :value="myStats.pending_verify" label="待我验证" @click="goToBugs('pending_verify')" />
      </el-col>
      <el-col :span="6">
        <StatCard tone="purple" :icon="Document" :value="myStats.created_today" label="今日新建" :clickable="false" />
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 我的 Bug 列表 -->
      <el-col :span="16">
        <el-card class="bug-list-card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <el-tabs v-model="bugTab" @tab-change="onTabChange" class="dash-tabs">
                <el-tab-pane label="指派给我" name="assigned" />
                <el-tab-pane label="我提交的" name="reported" />
                <el-tab-pane label="待我验证" name="pending_verify" />
              </el-tabs>
              <span class="view-all-btn" @click="goToBugListTab">
                查看全部 <el-icon><ArrowRight /></el-icon>
              </span>
            </div>
          </template>

          <div :style="{ minHeight: '200px', opacity: bugsLoading ? 0.4 : 1, transition: 'opacity 0.2s ease' }">
            <el-empty
              v-if="myBugList.length === 0 && !bugsLoading"
              description="暂无相关 Bug"
              :image-size="80"
              style="padding:24px 0;"
            />
            <div
              v-for="bug in myBugList"
              :key="bug.id"
              class="bug-item"
              @click="$router.push(`/bugs/${bug.id}`)"
            >
              <div class="bug-item__left">
                <span class="bug-item__id">BUG-{{ bug.id }}</span>
                <span class="bug-item__title">{{ bug.title }}</span>
              </div>
              <div class="bug-item__right">
                <StatusTag :status="bug.status" />
                <PriorityTag :priority="bug.priority" />
              </div>
            </div>

            <div v-if="bugTotal > pageSize" style="text-align:right;margin-top:12px;">
              <el-pagination
                v-model:current-page="bugPage"
                :total="bugTotal"
                :page-size="pageSize"
                layout="prev, pager, next"
                @current-change="loadMyBugs"
                small
              />
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：快捷操作 + 最近动态 -->
      <el-col :span="8">
        <!-- 快捷操作 -->
        <el-card class="quick-card" style="margin-bottom:16px;">
          <template #header><span class="card-header-title">快捷操作</span></template>
          <div class="quick-actions">
            <div class="quick-action-item" @click="$router.push('/bugs/create')">
              <el-icon class="quick-action-icon" color="var(--accent-lime)"><Plus /></el-icon>
              <span>新建 Bug</span>
            </div>
            <div class="quick-action-item" @click="goToBugs('assigned')">
              <el-icon class="quick-action-icon" color="var(--color-warning)"><User /></el-icon>
              <span>指派给我</span>
            </div>
            <div class="quick-action-item" @click="goToBugs('pending_verify')">
              <el-icon class="quick-action-icon" color="var(--color-success)"><Check /></el-icon>
              <span>待我验证</span>
            </div>
            <div class="quick-action-item" @click="$router.push('/stats')">
              <el-icon class="quick-action-icon" color="var(--text-muted)"><TrendCharts /></el-icon>
              <span>统计报表</span>
            </div>
          </div>
        </el-card>

        <!-- 最近动态 -->
        <el-card :style="{ opacity: activityLoading ? 0.4 : 1, transition: 'opacity 0.2s ease' }">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span class="card-header-title">最近动态</span>
              <span class="activity-subtitle">我的操作记录</span>
            </div>
          </template>
          <el-empty
            v-if="recentActivity.length === 0 && !activityLoading"
            description="暂无动态"
            :image-size="60"
            style="padding:16px 0;"
          />
          <div class="activity-timeline">
            <div
              v-for="item in recentActivity"
              :key="item.id"
              class="activity-item"
              @click="$router.push(`/bugs/${item.bug_id}`)"
            >
              <div class="activity-dot" :class="activityDotClass(item)" />
              <div class="activity-content">
                <div class="activity-main">
                  <span class="activity-bug-id">BUG-{{ item.bug_id }}</span>
                  <span class="activity-desc">{{ formatActivity(item) }}</span>
                </div>
                <div class="activity-time">{{ formatTime(item.created_at) }}</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/project'
import { statsApi } from '@/api'
import StatusTag from '@/components/StatusTag.vue'
import PriorityTag from '@/components/PriorityTag.vue'
import StatCard from '@/components/StatCard.vue'
import { Plus, User, EditPen, Check, Document, ArrowRight, TrendCharts } from '@element-plus/icons-vue'

const router = useRouter()
const auth   = useAuthStore()
const projectStore = useProjectStore()

// 当前筛选项目：仅在下拉选中具体项目（>0）时生效；未选/全部项目 → 跨项目视图
function currentPid(): number | undefined {
  const pid = projectStore.currentProjectId
  return pid > 0 ? pid : undefined
}

const myStats         = ref({ assigned_to_me: 0, reported_by_me: 0, pending_verify: 0, created_today: 0 })
const myBugList       = ref<any[]>([])
const recentActivity  = ref<any[]>([])
const bugTab          = ref('assigned')
const bugPage         = ref(1)
const bugTotal        = ref(0)
const pageSize        = 10
const bugsLoading     = ref(false)
const activityLoading = ref(false)

// ── 欢迎语 ──────────────────────────────────────────
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6)  return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayStr = computed(() => {
  const d = new Date()
  const days = ['周日','周一','周二','周三','周四','周五','周六']
  return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日 ${days[d.getDay()]}`
})

// ── 数据加载 ─────────────────────────────────────────
async function loadStats() {
  try {
    const res = await statsApi.mySummary(currentPid()) as any
    myStats.value = res
  } catch {}
}

async function loadMyBugs() {
  bugsLoading.value = true
  try {
    const res = await statsApi.myBugs(bugTab.value, bugPage.value, pageSize, currentPid()) as any
    myBugList.value = res.items
    bugTotal.value  = res.total
  } catch {}
  bugsLoading.value = false
}

async function loadRecentActivity() {
  activityLoading.value = true
  try {
    recentActivity.value = await statsApi.recentActivity(15, currentPid()) as any[]
  } catch {}
  activityLoading.value = false
}

function onTabChange(tab: string) {
  bugTab.value  = tab
  bugPage.value = 1
  loadMyBugs()
}

// ── 跳转 ─────────────────────────────────────────────
function goToBugs(type: 'assigned' | 'reported' | 'pending_verify') {
  if (type === 'assigned') {
    router.push({ path: '/bugs', query: { assignee_me: '1' } })
  } else if (type === 'reported') {
    router.push({ path: '/bugs', query: { reporter_id: String(auth.user?.id) } })
  } else {
    router.push({ path: '/bugs', query: { status_list: 'resolved', reporter_id: String(auth.user?.id) } })
  }
}

function goToBugListTab() {
  if (bugTab.value === 'assigned')      goToBugs('assigned')
  else if (bugTab.value === 'reported') goToBugs('reported')
  else                                  goToBugs('pending_verify')
}

// ── 动态格式化 ────────────────────────────────────────
const STATUS_LABEL: Record<string, string> = {
  new: '新建', assigned: '已指派', in_progress: '处理中',
  resolved: '待验证', closed: '已关闭', rejected: '已拒绝', reopened: '重新打开',
}
const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low',
}
const PRIORITY_LABEL: Record<string, string> = {
  p0: 'P0', p1: 'P1', p2: 'P2', p3: 'P3',
}
const FIELD_LABELS: Record<string, string> = {
  status: '状态', assignee_id: '指派人', priority: '优先级',
  severity: '严重度', reject_reason: '拒绝原因', fix_description: '修复说明',
  title: '标题', description: '描述',
}

function humanizeValue(field: string, val: string | null): string {
  if (!val) return '空'
  if (field === 'status')   return STATUS_LABEL[val]   || val
  if (field === 'severity') return SEVERITY_LABEL[val] || val
  if (field === 'priority') return PRIORITY_LABEL[val] || val
  return val
}

function formatActivity(item: any): string {
  // 创建 Bug（history.comment = "创建 Bug"）
  if (item.field_name === 'status' && item.comment === '创建 Bug') return '创建了 Bug'
  // 创建时指派（history.comment = "创建时指派"，new_value 已由后端转为 display_name）
  if (item.field_name === 'assignee_id' && item.comment === '创建时指派') {
    return item.new_value ? `指派给 ${item.new_value}` : '指派 Bug'
  }
  // 状态流转（不带备注）
  if (item.field_name === 'status' && item.old_value && item.new_value) {
    return `${STATUS_LABEL[item.old_value] || item.old_value} → ${STATUS_LABEL[item.new_value] || item.new_value}`
  }
  // 评论 / 备注
  if (item.comment) return '添加评论'
  // 其他字段变更
  const field = FIELD_LABELS[item.field_name] || item.field_name
  if (item.old_value && item.new_value) {
    return `${field}：${humanizeValue(item.field_name, item.old_value)} → ${humanizeValue(item.field_name, item.new_value)}`
  }
  if (item.new_value) return `设置${field}：${humanizeValue(item.field_name, item.new_value)}`
  return `操作了 ${field}`
}

function activityDotClass(item: any): string {
  if (item.field_name === 'assignee_id') return 'dot--assign'
  if (item.field_name === 'status') return 'dot--status'
  if (item.comment) return 'dot--comment'
  return 'dot--default'
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d  = new Date(iso)
  const now = new Date()
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000)
  if (diffMin < 1)  return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24)  return `${diffH} 小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7)   return `${diffD} 天前`
  return iso.slice(0, 10)
}

// ── 初始化 ────────────────────────────────────────────
onMounted(() => {
  loadStats()
  loadMyBugs()
  loadRecentActivity()
})

// 顶部「当前项目」下拉切换时刷新工作台数据
watch(() => projectStore.currentProjectId, async () => {
  bugPage.value = 1
  await Promise.all([loadStats(), loadMyBugs(), loadRecentActivity()])
})
</script>

<style scoped>
.dashboard {
  padding: 4px 0;
}

/* ── 欢迎栏 ── */
.welcome-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.welcome-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.greeting {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}
.date-info {
  font-size: 13px;
  color: var(--text-muted);
}

/* ── Bug 列表卡片 ── */
.bug-list-card :deep(.el-card__header) {
  padding-bottom: 0;
}
.dash-tabs {
  margin-bottom: -18px;
}

.bug-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s;
}
.bug-item:last-child { border-bottom: none; }
.bug-item:hover { background: var(--bg-surface-2); }
.bug-item__left {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}
.bug-item__id {
  font-family: var(--font-mono);
  color: var(--accent-violet);
  font-size: 12px;
  flex-shrink: 0;
}
.bug-item__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: var(--text-primary);
}
.bug-item__right {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 8px;
}

/* ── 卡片标题 ── */
.card-header-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── 查看全部按钮 ── */
.view-all-btn {
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--accent-lime);
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 6px;
  border-radius: 4px;
  transition: opacity 0.15s;
  user-select: none;
}
.view-all-btn:hover { opacity: 0.75; }

/* ── 快捷操作 ── */
.quick-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.quick-action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  background: var(--bg-surface-2);
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background 0.15s, transform 0.1s;
}
.quick-action-item:hover {
  background: var(--bg-surface-3);
  transform: translateY(-1px);
}
.quick-action-icon {
  font-size: 18px;
}

/* ── 最近动态时间线 ── */
.activity-subtitle {
  font-size: 12px;
  color: var(--text-muted);
}
.activity-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 4px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.12s;
}
.activity-item:last-child { border-bottom: none; }
.activity-item:hover { background: var(--bg-surface-2); }

.activity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}
.dot--status  { background: var(--accent-violet); }
.dot--assign  { background: var(--color-warning); }
.dot--comment { background: var(--color-success); }
.dot--default { background: var(--border-strong); }

.activity-content {
  flex: 1;
  min-width: 0;
}
.activity-main {
  display: flex;
  gap: 6px;
  align-items: baseline;
  flex-wrap: wrap;
}
.activity-bug-id {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--accent-violet);
  flex-shrink: 0;
  font-weight: 600;
}
.activity-desc {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.activity-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
