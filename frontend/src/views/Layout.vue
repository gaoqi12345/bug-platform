<template>
  <el-container style="min-height: 100vh;">
    <!-- 侧边栏 — Linear 风格，跟随主题（深色略深 / 浅色浅灰） -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <span class="logo-bug">🐛</span>
        <span class="logo-text">Bug Platform</span>
        <span class="logo-dot" />
      </div>

      <el-menu
        :default-active="$route.path"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><House /></el-icon><span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/testcases">
          <el-icon><Document /></el-icon><span>测试用例</span>
        </el-menu-item>
        <el-menu-item index="/bugs">
          <el-icon><List /></el-icon><span>Bug 列表</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><DataLine /></el-icon><span>统计报表</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon><span>项目设置</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isSuperAdmin" index="/admin">
          <el-icon><Tools /></el-icon><span>系统管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="main-container">
      <!-- 顶部栏 -->
      <el-header class="app-header">
        <!-- Left: project selector -->
        <div class="header-left">
          <span class="project-label">当前项目：</span>
          <el-select
            v-model="projectStore.currentProjectId"
            placeholder="请选择项目"
            style="width: 200px;"
            @change="onProjectChange"
          >
            <el-option
              :key="ALL_PROJECTS"
              :value="ALL_PROJECTS"
              label="全部项目"
              :style="{ fontWeight: 500 }"
            />
            <el-option
              v-for="p in projects"
              :key="p.id"
              :label="p.status === 'archived' ? `[归档] ${p.name}` : p.name"
              :value="p.id"
              :style="p.status === 'archived' ? { color: 'var(--text-secondary)' } : {}"
            />
          </el-select>
          <el-tag
            v-if="projectStore.isCurrentProjectArchived"
            type="info"
            size="small"
            class="archived-tag"
          >已归档 · 只读</el-tag>
        </div>

        <!-- Right: theme toggle + user dropdown -->
        <div class="header-right">
          <el-button
            circle
            size="small"
            class="theme-toggle"
            @click="themeStore.toggle()"
          >
            <el-icon v-if="themeStore.mode === 'dark'"><Sunny /></el-icon>
            <el-icon v-else><Moon /></el-icon>
          </el-button>

          <el-dropdown @command="handleCommand">
            <span class="user-trigger">
              <el-avatar size="small" class="user-avatar">
                {{ auth.user?.display_name?.charAt(0) }}
              </el-avatar>
              <span class="user-name">{{ auth.user?.display_name }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人设置</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { House, List, DataLine, Setting, ArrowDown, Tools, Document, Moon, Sunny } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore, ALL_PROJECTS } from '@/stores/project'
import { projectApi, authApi } from '@/api'
import { usePermissionConfigStore } from '@/stores/permissionConfig'
import { useRbacStore } from '@/stores/rbac'
import { useThemeStore } from '@/stores/theme'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const projectStore = useProjectStore()
const permConfigStore = usePermissionConfigStore()
const rbacStore = useRbacStore()
const themeStore = useThemeStore()
const projects = ref<any[]>([])

async function loadProjects() {
  try {
    // 普通用户只拉活跃项目；super_admin 通过 Admin 页面查看归档，这里也只拉活跃
    const list = await projectApi.list() as any[]
    projects.value = list
    projectStore.projects = list
    if (!projectStore.currentProjectId && list.length > 0) {
      projectStore.setCurrentProject(list[0].id)
    }
    // 如果当前选中的是归档项目（从 Admin 页跳过来的），也要把它加入 store
    // （「全部项目」哨兵值 -1 不需要归档重拉）
    const currentId = projectStore.currentProjectId
    if (currentId > 0 && !list.find((p: any) => p.id === currentId)) {
      // 当前项目不在活跃列表里，可能是归档项目，单独拉一次全量
      const allList = await projectApi.list(true) as any[]
      projectStore.projects = allList
      projects.value = allList
    }
  } catch {}
}

onMounted(() => {
  // 刷新当前用户信息（确保 display_name 等字段最新，防止 localStorage 缓存旧数据）
  authApi.me().then((u: any) => {
    auth.user = u
    localStorage.setItem('user', JSON.stringify(u))
  }).catch(() => {})
  loadProjects()
  permConfigStore.load()
  rbacStore.load()
})

// 从系统管理页面离开时重新拉取（新增项目后立即可选）
watch(() => route.path, (newPath, oldPath) => {
  if (oldPath?.startsWith('/admin')) {
    loadProjects()
  }
})

function onProjectChange(id: number) {
  projectStore.setCurrentProject(id)
}

function handleCommand(cmd: string) {
  if (cmd === 'profile') {
    router.push('/profile')
  } else if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════════
   SIDEBAR — Linear 风格，跟随主题
   ═══════════════════════════════════════════════════════════════ */

.sidebar {
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-subtle);
  flex-shrink: 0;
  overflow: hidden;
}

/* ── Logo ─────────────────────────────────────────────────────── */

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px 20px 18px;
  border-bottom: 1px solid var(--border-subtle);
}

.logo-bug {
  font-size: 19px;
  line-height: 1;
}

.logo-text {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.025em;
  flex: 1;
}

.logo-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-lime);
  flex-shrink: 0;
  align-self: flex-start;
  margin-top: 3px;
}

/* ── Menu shell ───────────────────────────────────────────────── */

:deep(.sidebar-menu) {
  background: var(--bg-sidebar) !important;
  border-right: none !important;
  padding: 8px 0;
}

/* All items: muted default state */
:deep(.sidebar-menu .el-menu-item) {
  background: transparent !important;
  color: var(--text-secondary) !important;
  height: 40px;
  line-height: 40px;
  margin: 2px 10px;
  border-radius: 6px;
  padding-left: 14px !important;
  transition: background 0.15s ease, color 0.15s ease;
}

:deep(.sidebar-menu .el-menu-item .el-icon) {
  color: var(--text-secondary) !important;
  transition: color 0.15s ease;
}

/* Hover */
:deep(.sidebar-menu .el-menu-item:hover) {
  background: var(--bg-surface-2) !important;
  color: var(--text-primary) !important;
}

:deep(.sidebar-menu .el-menu-item:hover .el-icon) {
  color: var(--text-primary) !important;
}

/* Active — 扁平化：浅背景 + 主文字，无彩色竖条 */
:deep(.sidebar-menu .el-menu-item.is-active) {
  background: var(--bg-surface-3) !important;
  color: var(--text-primary) !important;
}

:deep(.sidebar-menu .el-menu-item.is-active .el-icon) {
  color: var(--accent-lime) !important;
}

/* ═══════════════════════════════════════════════════════════════
   HEADER — adapts to theme via CSS variables
   ═══════════════════════════════════════════════════════════════ */

.main-container {
  overflow: hidden;
  min-width: 0;
}

.app-header {
  background: var(--bg-header);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
  transition: background 0.2s ease, border-color 0.2s ease;
}

/* Left cluster */
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.project-label {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.archived-tag {
  margin-left: 2px;
}

/* Right cluster */
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Theme toggle ─────────────────────────────────────────────── */

.theme-toggle {
  border-color: var(--border-subtle) !important;
  background: transparent !important;
  color: var(--text-secondary) !important;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.theme-toggle:hover {
  border-color: var(--accent-lime) !important;
  color: var(--accent-lime) !important;
  background: var(--bg-surface-2) !important;
}

/* ── User dropdown trigger ────────────────────────────────────── */

.user-trigger {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 8px;
  border-radius: 6px;
  color: var(--text-primary);
  transition: background 0.15s;
}

.user-trigger:hover {
  background: var(--bg-surface-2);
}

.user-avatar {
  background: var(--accent-lime) !important;
  flex-shrink: 0;
}

.user-name {
  font-size: 14px;
  color: var(--text-primary);
}

/* ═══════════════════════════════════════════════════════════════
   MAIN CANVAS — adapts to theme
   ═══════════════════════════════════════════════════════════════ */

.app-main {
  background: var(--bg-canvas);
  overflow-y: auto;
  transition: background 0.2s ease;
  min-height: 100%;
}

/* Ensure the el-container stretches full height */
:deep(.el-container) {
  min-height: 100vh;
}

</style>
