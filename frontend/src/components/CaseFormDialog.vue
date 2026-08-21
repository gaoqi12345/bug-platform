<template>
  <el-dialog
    :model-value="modelValue"
    :title="editingCase ? '编辑用例' : '新建用例'"
    width="700px"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="resetCaseForm"
  >
    <el-form :model="caseForm" label-width="90px">
      <el-form-item label="标题" required>
        <el-input v-model="caseForm.title" placeholder="用例标题" />
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="caseForm.priority" style="width:120px">
          <el-option v-for="p in CASE_PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="前置条件">
        <el-input v-model="caseForm.precondition" type="textarea" :rows="2"
          placeholder="执行前需要满足的条件（可选）" />
      </el-form-item>
      <el-form-item label="测试步骤">
        <RichEditor v-model="caseForm.steps" placeholder="1. 打开登录页&#10;2. 输入账号密码&#10;3. 点击登录" min-height="120px" />
      </el-form-item>
      <el-form-item label="预期结果">
        <RichEditor v-model="caseForm.expected_result" placeholder="执行后应该看到的结果，可粘贴截图" min-height="80px" />
      </el-form-item>
      <el-form-item v-if="editingCase" label="状态">
        <el-switch v-model="caseForm.is_deprecated" active-text="已废弃" inactive-text="有效" />
      </el-form-item>
    </el-form>
    <template #footer>
      <div style="display:flex; justify-content:space-between; align-items:center; width:100%">
        <el-button v-if="editingCase" type="danger" plain :loading="saving" @click="deleteCase">删除用例</el-button>
        <div style="display:flex; gap:8px; margin-left:auto">
          <el-button @click="close">取消</el-button>
          <el-button type="primary" :loading="saving" @click="submitCase">保存</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { testCaseApi } from '@/api'
import RichEditor from '@/components/RichEditor.vue'
import { CASE_PRIORITY_OPTIONS } from '@/utils/caseConstants'

const props = defineProps<{
  modelValue: boolean
  editingCase: any | null
  projectId: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  saved: []
}>()

const saving = ref(false)
const caseForm = reactive({
  title: '', precondition: '', steps: '', expected_result: '',
  priority: 'P2', is_deprecated: false,
})

// 打开对话框时同步表单（新建则重置，编辑则填充）
watch(() => props.modelValue, (open) => {
  if (!open) return
  if (props.editingCase) {
    Object.assign(caseForm, {
      title:           props.editingCase.title,
      precondition:    props.editingCase.precondition || '',
      steps:           props.editingCase.steps || '',
      expected_result: props.editingCase.expected_result || '',
      priority:        props.editingCase.priority,
      is_deprecated:   props.editingCase.is_deprecated,
    })
  } else {
    resetCaseForm()
  }
})

function resetCaseForm() {
  Object.assign(caseForm, {
    title: '', precondition: '', steps: '', expected_result: '',
    priority: 'P2', is_deprecated: false,
  })
}

function close() {
  emit('update:modelValue', false)
}

async function submitCase() {
  const pid = props.projectId
  if (!pid || !caseForm.title.trim()) { ElMessage.warning('请填写用例标题'); return }
  saving.value = true
  try {
    if (props.editingCase) {
      await testCaseApi.update(pid, props.editingCase.id, { ...caseForm })
      ElMessage.success('用例已更新')
    } else {
      await testCaseApi.create(pid, { ...caseForm })
      ElMessage.success('用例创建成功')
    }
    close()
    emit('saved')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '操作失败')
  } finally {
    saving.value = false
  }
}

async function deleteCase() {
  if (!props.editingCase) return
  try {
    await ElMessageBox.confirm(
      `确认删除用例「${props.editingCase.title}」？此操作不可恢复。`,
      '删除用例',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
    )
  } catch { return }
  const pid = props.projectId
  if (!pid) return
  saving.value = true
  try {
    await testCaseApi.delete(pid, props.editingCase.id)
    ElMessage.success('用例已删除')
    close()
    emit('saved')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '删除失败')
  } finally {
    saving.value = false
  }
}
</script>
