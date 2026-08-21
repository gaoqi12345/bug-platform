<template>
  <div style="max-width: 800px; margin: 0 auto; padding: 0 0 40px">
    <el-card>
      <template #header>
        <span class="page-title">新建 Bug</span>
      </template>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px" class="bug-create-form">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入 Bug 标题" />
        </el-form-item>
        <el-form-item label="严重度" prop="severity">
          <el-select v-model="form.severity" style="width:100%">
            <el-option v-for="s in SEVERITY_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="form.priority" style="width:100%">
            <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属版本">
          <el-select v-model="form.found_in_version_id" clearable placeholder="请选择版本" style="width:100%">
            <el-option v-for="v in versions" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="指派给">
          <el-select v-model="form.assignee_id" clearable placeholder="可选，创建后再指派" style="width:100%">
            <el-option v-for="m in projectMembers" :key="m.user_id" :label="m.display_name" :value="m.user_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <RichEditor v-model="form.description" placeholder="详细描述 Bug，可 Ctrl+V 粘贴截图" min-height="90px" />
        </el-form-item>
        <el-form-item label="重现步骤">
          <RichEditor v-model="form.steps_to_reproduce" placeholder="Step 1: ...&#10;Step 2: ...&#10;Step 3: ..." min-height="100px" />
        </el-form-item>
        <el-form-item label="预期结果">
          <RichEditor v-model="form.expected_result" placeholder="应该发生什么，可 Ctrl+V 粘贴截图" min-height="70px" />
        </el-form-item>
        <el-form-item label="实际结果">
          <RichEditor v-model="form.actual_result" placeholder="实际发生了什么，可 Ctrl+V 粘贴截图" min-height="70px" />
        </el-form-item>
        <el-form-item label="环境信息">
          <el-input v-model="form.environment" placeholder="如：Windows 11 / Chrome 125 / v1.0.2" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="handleSubmit">提交 Bug</el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useProjectStore, ALL_PROJECTS } from '@/stores/project'
import { bugApi, versionApi, projectApi } from '@/api'
import { SEVERITY_OPTIONS, PRIORITY_OPTIONS } from '@/utils/status'
import RichEditor from '@/components/RichEditor.vue'

const router = useRouter()
const projectStore = useProjectStore()
const formRef = ref()
const loading = ref(false)
const versions = ref<any[]>([])
const projectMembers = ref<any[]>([])

const form = reactive({
  title: '',
  description: '',
  steps_to_reproduce: '',
  expected_result: '',
  actual_result: '',
  environment: '',
  severity: 'medium',
  priority: 'p2',
  found_in_version_id: null as number | null,
  assignee_id: null as number | null,
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  severity: [{ required: true, message: '请选择严重度', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
}

onMounted(async () => {
  const pid = projectStore.currentProjectId
  if (pid && pid !== ALL_PROJECTS) {
    try {
      const [vlist, members] = await Promise.all([
        versionApi.list(pid) as any[],
        projectApi.listMembers(pid) as any[],
      ])
      versions.value = vlist
      projectMembers.value = members
    } catch {}
  }
})

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  const pid = projectStore.currentProjectId
  if (!pid || pid === ALL_PROJECTS) { ElMessage.error('请先选择项目'); return }
  loading.value = true
  try {
    const bug = await bugApi.create(pid, form) as any
    if (!bug?.id) { ElMessage.error('创建失败：返回数据异常'); return }
    ElMessage.success('Bug 创建成功')
    router.push(`/bugs/${bug.id}`)
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '创建失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 700;
}

.page-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--accent-lime);
  border-radius: 2px;
  margin-right: 10px;
  vertical-align: middle;
}

.bug-create-form :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
}
</style>
