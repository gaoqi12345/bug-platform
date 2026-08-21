<template>
  <div>
    <el-tabs v-model="activeTab">
      <!-- ── 团队管理 ── -->
      <el-tab-pane label="团队管理" name="teams">
        <TeamsTab />
      </el-tab-pane>

      <!-- ── 项目管理 ── -->
      <el-tab-pane label="项目管理" name="projects">
        <ProjectsTab />
      </el-tab-pane>

      <!-- ── 用户管理 ── -->
      <el-tab-pane label="用户管理" name="users">
        <UsersTab />
      </el-tab-pane>

      <!-- ── 流程管理 ── -->
      <el-tab-pane label="流程管理" name="workflow">
        <WorkflowTab />
      </el-tab-pane>

      <!-- ── 角色管理 ── -->
      <el-tab-pane label="角色管理" name="roles">
        <RolesTab />
      </el-tab-pane>

      <!-- ── 系统设置 ── -->
      <el-tab-pane label="系统设置" name="system">
        <SystemTab />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TeamsTab from './admin/TeamsTab.vue'
import ProjectsTab from './admin/ProjectsTab.vue'
import UsersTab from './admin/UsersTab.vue'
import WorkflowTab from './admin/WorkflowTab.vue'
import RolesTab from './admin/RolesTab.vue'
import SystemTab from './admin/SystemTab.vue'

const activeTab = ref('teams')
</script>
