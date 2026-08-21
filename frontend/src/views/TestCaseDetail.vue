<template>
  <div class="case-detail">
    <div v-if="detailCase" class="detail-content">
      <!-- 顶部：返回 + 标题 + 操作 -->
      <div class="detail-header">
        <el-button class="back-btn" size="small" @click="router.back()">
          <el-icon style="margin-right:4px;"><ArrowLeft /></el-icon>返回
        </el-button>
        <div class="case-title-row">
          <span class="case-id">CASE-{{ detailCase.id }}</span>
          <h2 class="case-title">{{ detailCase.title }}</h2>
          <el-tag :style="CASE_PRIORITY_STYLE[detailCase.priority] || CASE_PRIORITY_STYLE['P2']" size="small">
            {{ detailCase.priority?.toUpperCase() }}
          </el-tag>
          <el-tag v-if="detailCase.project_name" type="info" size="small">{{ detailCase.project_name }}</el-tag>
        </div>
        <div class="case-actions">
          <el-button type="primary" size="small" @click="openRun">执行此用例</el-button>
          <el-button size="small" @click="openEdit">编辑用例</el-button>
        </div>
      </div>

      <!-- 基本信息 -->
      <el-descriptions :column="2" border size="small" style="margin-bottom:16px;">
        <el-descriptions-item label="优先级">
          <el-tag :style="CASE_PRIORITY_STYLE[detailCase.priority] || CASE_PRIORITY_STYLE['P2']">
            {{ detailCase.priority?.toUpperCase() }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="所属项目">{{ detailCase.project_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ detailCase.creator_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ detailCase.created_at?.slice(0,19).replace('T',' ') }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detailCase.is_deprecated" label="状态">
          <el-tag type="danger" size="small">已废弃</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 前置条件 -->
      <template v-if="detailCase.precondition">
        <div class="detail-section-title">前置条件</div>
        <div class="detail-text" style="white-space:pre-wrap;">{{ detailCase.precondition }}</div>
      </template>

      <!-- 测试步骤 -->
      <div class="detail-section-title">测试步骤</div>
      <div v-if="detailCase.steps" class="rich-preview" v-html="sanitizeHtml(detailCase.steps)" />
      <div v-else class="detail-empty">（未填写）</div>

      <!-- 预期结果 -->
      <div class="detail-section-title">预期结果</div>
      <div v-if="detailCase.expected_result" class="rich-preview" v-html="sanitizeHtml(detailCase.expected_result)" />
      <div v-else class="detail-empty">（未填写）</div>

      <!-- 执行历史 -->
      <div class="detail-section-title">执行历史</div>
      <div v-if="caseRuns.length === 0" class="detail-empty">暂无执行记录</div>
      <el-timeline v-else>
        <el-timeline-item
          v-for="run in caseRuns"
          :key="run.id"
          :timestamp="run.executed_at?.slice(0,19).replace('T',' ')"
          placement="top"
        >
          <div class="run-row">
            <el-tag :type="RUN_RESULT_TYPE[run.result]" size="small">
              {{ RUN_RESULT_LABEL[run.result] }}
            </el-tag>
            <span class="run-executor">{{ run.executor_name }}</span>
            <el-tag v-if="run.version_name" type="info" size="small">{{ run.version_name }}</el-tag>
            <el-tag v-if="run.bug_id" type="danger" size="small" class="run-bug-tag"
              @click="router.push(`/bugs/${run.bug_id}`)">
              Bug #{{ run.bug_id }}
            </el-tag>
          </div>
          <div v-if="run.actual_result" class="rich-preview run-actual"
            v-html="sanitizeHtml(run.actual_result)" />
        </el-timeline-item>
      </el-timeline>

      <!-- 执行 / 编辑对话框 -->
      <RunDialog
        v-model="showRunDialog"
        :running-case="detailCase"
        :project-id="detailCase.project_id"
        :versions="versions"
        :project-bugs="projectBugs"
        @submitted="onRunSubmitted"
      />
      <CaseFormDialog
        v-model="showCaseDialog"
        :editing-case="detailCase"
        :project-id="detailCase.project_id"
        @saved="onCaseSaved"
      />
    </div>

    <!-- 加载失败 / 无权限 -->
    <div v-else-if="loadFailed" class="detail-empty" style="text-align:center; padding:80px 0;">
      <p style="font-size:15px; color:var(--text-secondary);">用例不存在或无权访问</p>
      <el-button style="margin-top:12px;" @click="router.back()">返回</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { testCaseApi, versionApi, bugApi } from '@/api'
import RunDialog from '@/components/RunDialog.vue'
import CaseFormDialog from '@/components/CaseFormDialog.vue'
import { sanitizeHtml } from '@/utils/sanitize'
import { CASE_PRIORITY_STYLE, RUN_RESULT_LABEL, RUN_RESULT_TYPE } from '@/utils/caseConstants'

const route = useRoute()
const router = useRouter()

const caseId     = Number(route.params.id)
const detailCase = ref<any>(null)
const caseRuns   = ref<any[]>([])
const versions   = ref<any[]>([])
const projectBugs = ref<any[]>([])
const loadFailed = ref(false)

const showRunDialog  = ref(false)
const showCaseDialog = ref(false)

async function load() {
  try {
    const c = await testCaseApi.getById(caseId) as any
    detailCase.value = c
    const [runs, vlist, bugs] = await Promise.all([
      testCaseApi.listRunsById(caseId) as any[],
      versionApi.list(c.project_id) as any[],
      bugApi.list({ project_id: c.project_id, page: 1, page_size: 100 }) as any,
    ])
    caseRuns.value  = runs
    versions.value  = vlist
    projectBugs.value = bugs.items ?? []
  } catch {
    loadFailed.value = true
  }
}

onMounted(load)

function openRun() {
  showRunDialog.value = true
}

function openEdit() {
  showCaseDialog.value = true
}

async function onRunSubmitted() {
  try { caseRuns.value = await testCaseApi.listRunsById(caseId) as any[] } catch {}
}

async function onCaseSaved() {
  try { detailCase.value = await testCaseApi.getById(caseId) as any } catch {}
}
</script>

<style scoped>
.case-detail {
  max-width: 900px;
  margin: 0 auto;
  padding: 8px 4px 40px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
}

.back-btn { margin-top: 4px; }

.case-title-row {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-width: 0;
}

.case-id {
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  color: var(--text-muted);
}

.case-title {
  margin: 0;
  font-size: 20px;
  color: var(--text-primary);
  word-break: break-word;
}

.case-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.detail-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 18px 0 8px;
  padding-left: 6px;
  border-left: 3px solid var(--accent-lime);
}

.detail-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.detail-empty {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.run-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.run-executor { font-size: 13px; color: var(--text-secondary); }

.run-bug-tag { cursor: pointer; }

.run-actual {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.rich-preview {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
}
.rich-preview :deep(p) { margin: 0 0 4px; }
.rich-preview :deep(p:last-child) { margin-bottom: 0; }
.rich-preview :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  border: 1px solid var(--border-subtle);
  margin: 4px 0;
  display: block;
}
.rich-preview :deep(ul),
.rich-preview :deep(ol) { padding-left: 20px; margin: 4px 0; }
.rich-preview :deep(code) {
  background: var(--bg-surface-2);
  border-radius: 3px;
  padding: 1px 4px;
  font-size: 12px;
  color: var(--color-warning);
  font-family: var(--font-mono, monospace);
}
</style>
