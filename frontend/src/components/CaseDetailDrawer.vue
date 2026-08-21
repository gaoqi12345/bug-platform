<template>
  <el-drawer
    :model-value="modelValue"
    :title="detailCase?.title"
    size="560px"
    direction="rtl"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="detailCase" style="padding: 0 4px;">
      <!-- 基本信息 -->
      <el-descriptions :column="2" border size="small" style="margin-bottom:16px;">
        <el-descriptions-item label="优先级">
          <el-tag :style="CASE_PRIORITY_STYLE[detailCase.priority] || CASE_PRIORITY_STYLE['P2']">
            {{ detailCase.priority?.toUpperCase() }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ detailCase.creator_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">
          {{ detailCase.created_at?.slice(0,19).replace('T',' ') }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- 前置条件 -->
      <template v-if="detailCase.precondition">
        <div class="detail-section-title">前置条件</div>
        <div style="font-size:14px; color:var(--text-secondary); margin-bottom:16px; white-space:pre-wrap;">
          {{ detailCase.precondition }}
        </div>
      </template>

      <!-- 测试步骤 -->
      <div class="detail-section-title">测试步骤</div>
      <div v-if="detailCase.steps" class="rich-preview" v-html="sanitizeHtml(detailCase.steps)"
        style="margin-bottom:16px;" />
      <div v-else style="color:var(--text-muted); font-size:13px; margin-bottom:16px;">（未填写）</div>

      <!-- 预期结果 -->
      <div class="detail-section-title">预期结果</div>
      <div v-if="detailCase.expected_result" class="rich-preview" v-html="sanitizeHtml(detailCase.expected_result)"
        style="margin-bottom:16px;" />
      <div v-else style="color:var(--text-muted); font-size:13px; margin-bottom:16px;">（未填写）</div>

      <!-- 执行历史 -->
      <div class="detail-section-title">执行历史</div>
      <div v-if="caseRuns.length === 0" style="color:var(--text-muted); font-size:13px; margin-bottom:8px;">
        暂无执行记录
      </div>
      <el-timeline v-else>
        <el-timeline-item
          v-for="run in caseRuns"
          :key="run.id"
          :timestamp="run.executed_at?.slice(0,19).replace('T',' ')"
          placement="top"
        >
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <el-tag :type="RUN_RESULT_TYPE[run.result]" size="small">
              {{ RUN_RESULT_LABEL[run.result] }}
            </el-tag>
            <span style="font-size:13px;">{{ run.executor_name }}</span>
            <el-tag v-if="run.version_name" type="info" size="small">{{ run.version_name }}</el-tag>
            <el-tag v-if="run.bug_id" type="danger" size="small"
              style="cursor:pointer" @click="router.push(`/bugs/${run.bug_id}`)">
              Bug #{{ run.bug_id }}
            </el-tag>
          </div>
          <div v-if="run.actual_result" class="rich-preview"
            style="margin-top:6px; font-size:13px; color:var(--text-secondary);"
            v-html="sanitizeHtml(run.actual_result)" />
        </el-timeline-item>
      </el-timeline>

      <!-- 底部操作 -->
      <div style="margin-top:20px; display:flex; gap:8px;">
        <el-button type="primary" @click="emit('run')">执行此用例</el-button>
        <el-button @click="emit('edit')">编辑用例</el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { sanitizeHtml } from '@/utils/sanitize'
import { CASE_PRIORITY_STYLE, RUN_RESULT_LABEL, RUN_RESULT_TYPE } from '@/utils/caseConstants'

const router = useRouter()

defineProps<{
  modelValue: boolean
  detailCase: any | null
  caseRuns: any[]
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  run: []
  edit: []
}>()
</script>

<style scoped>
.detail-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  padding-left: 6px;
  border-left: 3px solid var(--accent-lime);
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
