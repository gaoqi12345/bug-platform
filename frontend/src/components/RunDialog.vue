<template>
  <el-dialog
    :model-value="modelValue"
    title="记录执行结果"
    width="620px"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="resetRunForm"
  >
    <div v-if="runningCase" style="margin-bottom:16px; padding:12px; background:var(--bg-surface-2); border-radius:4px; border:1px solid var(--border-subtle);">
      <div style="font-weight:600; margin-bottom:4px;">{{ runningCase.title }}</div>
      <div v-if="runningCase.steps" style="font-size:13px; color:var(--text-secondary);">
        <strong>步骤：</strong>
        <div class="rich-preview" v-html="sanitizeHtml(runningCase.steps)" />
      </div>
      <div v-if="runningCase.expected_result" style="font-size:13px; color:var(--text-secondary); margin-top:4px;">
        <strong>预期：</strong>
        <div class="rich-preview" v-html="sanitizeHtml(runningCase.expected_result)" />
      </div>
    </div>

    <el-form :model="runForm" label-width="90px">
      <el-form-item label="版本">
        <el-select v-model="runForm.version_id" clearable placeholder="选择版本（可选）" style="width:100%">
          <el-option v-for="v in versions" :key="v.id" :label="v.name" :value="v.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="执行结果" required>
        <el-radio-group v-model="runForm.result" @change="onResultChange">
          <el-radio-button value="passed">✅ 通过</el-radio-button>
          <el-radio-button value="failed">❌ 失败</el-radio-button>
          <el-radio-button value="blocked">⚠️ 阻塞</el-radio-button>
          <el-radio-button value="skipped">⏭ 跳过</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <!-- 阻塞时：显示实际结果（无 Bug 关联逻辑） -->
      <el-form-item v-if="runForm.result === 'blocked'" label="实际结果">
        <RichEditor v-model="runForm.actual_result" placeholder="描述阻塞原因，可 Ctrl+V 粘贴截图" min-height="80px" />
      </el-form-item>

      <!-- 失败时：关联或新建 Bug -->
      <template v-if="runForm.result === 'failed'">
        <el-divider>关联 Bug</el-divider>
        <el-form-item label="">
          <el-radio-group v-model="runForm.bugAction" style="margin-bottom:12px;">
            <el-radio value="none">不关联</el-radio>
            <el-radio value="existing">关联已有 Bug</el-radio>
            <el-radio value="create">创建新 Bug</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="runForm.bugAction === 'none'" label="实际结果">
          <RichEditor v-model="runForm.actual_result" placeholder="描述实际发生了什么，可 Ctrl+V 粘贴截图" min-height="80px" />
        </el-form-item>

        <template v-if="runForm.bugAction === 'existing'">
          <el-form-item label="实际结果">
            <RichEditor v-model="runForm.actual_result" placeholder="描述实际发生了什么，可 Ctrl+V 粘贴截图" min-height="80px" />
          </el-form-item>
          <el-form-item label="选择 Bug">
            <el-select v-model="runForm.bug_id" clearable filterable placeholder="搜索 Bug" style="width:100%">
              <el-option v-for="b in projectBugs" :key="b.id"
                :label="`#${b.id} ${b.title}`" :value="b.id" />
            </el-select>
          </el-form-item>
        </template>

        <template v-if="runForm.bugAction === 'create'">
          <el-form-item label="Bug 标题" required>
            <el-input v-model="newBugForm.title" placeholder="Bug 标题" />
          </el-form-item>
          <el-form-item label="严重度">
            <el-select v-model="newBugForm.severity" style="width:140px">
              <el-option label="严重 Critical" value="critical" />
              <el-option label="高 High" value="high" />
              <el-option label="中 Medium" value="medium" />
              <el-option label="低 Low" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="newBugForm.priority" style="width:140px">
              <el-option label="P0" value="p0" />
              <el-option label="P1" value="p1" />
              <el-option label="P2" value="p2" />
              <el-option label="P3" value="p3" />
            </el-select>
          </el-form-item>
          <el-form-item label="重现步骤">
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">已从测试用例步骤继承，可修改</div>
            <RichEditor v-model="newBugForm.steps_to_reproduce" min-height="80px" />
          </el-form-item>
          <el-form-item label="预期结果">
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">已从测试用例预期结果继承，可修改</div>
            <RichEditor v-model="newBugForm.expected_result" min-height="60px" />
          </el-form-item>
          <el-form-item label="实际结果">
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">将同时写入 Bug 和执行记录</div>
            <RichEditor v-model="newBugForm.actual_result" placeholder="实际发生了什么，可 Ctrl+V 粘贴截图" min-height="80px" />
          </el-form-item>
        </template>
      </template>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submitRun">提交结果</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { testCaseApi, bugApi } from '@/api'
import RichEditor from '@/components/RichEditor.vue'
import { sanitizeHtml } from '@/utils/sanitize'

const props = defineProps<{
  modelValue: boolean
  runningCase: any | null
  projectId: number | null
  versions: any[]
  projectBugs: any[]
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  submitted: [caseId: number]
}>()

const saving = ref(false)

const runForm = reactive({
  version_id:  null as number | null,
  result:      'passed',
  actual_result: '',
  bug_id:      null as number | null,
  bugAction:   'none' as 'none' | 'existing' | 'create',
})
const newBugForm = reactive({
  title: '', severity: 'medium', priority: 'p2',
  steps_to_reproduce: '', expected_result: '', actual_result: '',
})

function resetRunForm() {
  Object.assign(runForm, {
    version_id: null, result: 'passed', actual_result: '',
    bug_id: null, bugAction: 'none',
  })
  Object.assign(newBugForm, {
    title: '', severity: 'medium', priority: 'p2',
    steps_to_reproduce: '', expected_result: '', actual_result: '',
  })
}

// 切换结果时，若选失败则预填 newBugForm 内容
function onResultChange(val: string) {
  if (val === 'failed' && props.runningCase) {
    newBugForm.title              = props.runningCase.title || ''
    newBugForm.steps_to_reproduce = props.runningCase.steps || ''
    newBugForm.expected_result    = props.runningCase.expected_result || ''
    newBugForm.actual_result      = runForm.actual_result || ''
  }
}

async function submitRun() {
  const pid = props.projectId
  if (!pid || !props.runningCase) return
  if (!runForm.result) { ElMessage.warning('请选择执行结果'); return }
  saving.value = true
  try {
    let bugId = runForm.bug_id

    // 失败 + 创建新 Bug
    if (runForm.result === 'failed' && runForm.bugAction === 'create') {
      if (!newBugForm.title.trim()) { ElMessage.warning('请填写 Bug 标题'); saving.value = false; return }
      const bug = await bugApi.create(pid, {
        title:              newBugForm.title,
        severity:           newBugForm.severity,
        priority:           newBugForm.priority,
        steps_to_reproduce: newBugForm.steps_to_reproduce,
        expected_result:    newBugForm.expected_result,
        actual_result:      newBugForm.actual_result,
      }) as any
      bugId = bug.id
      ElMessage.success(`Bug #${bug.id} 已创建`)
    } else if (runForm.result === 'failed' && runForm.bugAction === 'existing') {
      bugId = runForm.bug_id
    } else {
      bugId = null
    }

    await testCaseApi.createRun(pid, props.runningCase.id, {
      version_id:    runForm.version_id,
      result:        runForm.result,
      // 创建新 Bug 时：实际结果来自 newBugForm，保证两处一致
      actual_result: runForm.result === 'failed' && runForm.bugAction === 'create'
        ? newBugForm.actual_result
        : runForm.actual_result,
      bug_id:        bugId,
    })
    ElMessage.success('执行结果已记录')
    emit('update:modelValue', false)
    emit('submitted', props.runningCase.id)
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '提交失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
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
