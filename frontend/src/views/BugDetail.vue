<template>
  <div class="bug-detail">
    <!-- Bug 基本信息 -->
    <div v-if="bug" class="bug-card">
      <div class="bug-header">
        <div class="bug-meta">
          <span class="bug-id">BUG-{{ bug.id }}</span>
          <h2 class="bug-title">{{ bug.title }}</h2>
        </div>
        <div class="bug-actions">
          <StatusTag :status="bug.status" size="default" />
          <!-- 状态流转按钮 -->
          <template v-for="action in availableActions" :key="action.action">
            <el-button
              :type="action.type as any"
              size="small"
              @click="handleAction(action.action)"
            >{{ action.label }}</el-button>
          </template>
          <!-- 删除按钮：仅限 NEW 状态 + 本人提交（或 super_admin） -->
          <el-button
            v-if="canDeleteBug"
            size="small"
            type="danger"
            plain
            @click="deleteBug"
          >删除</el-button>
        </div>
      </div>

      <div class="bug-body">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="严重度">
            <SeverityTag :severity="bug.severity" />
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <PriorityTag :priority="bug.priority" />
          </el-descriptions-item>
          <el-descriptions-item label="所属项目">{{ bug.project_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="提交人">{{ bug.reporter_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="指派给">{{ bug.assignee_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="发现版本">{{ versionName(bug.found_in_version_id) }}</el-descriptions-item>
          <el-descriptions-item label="修复版本">{{ versionName(bug.fixed_in_version_id) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ bug.created_at?.slice(0,19).replace('T',' ') }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">
            <div v-if="bug.description" class="rich-content" v-html="sanitizeHtml(bug.description)" />
            <span v-else class="muted-dash">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="重现步骤" :span="2">
            <div v-if="bug.steps_to_reproduce" class="rich-content" v-html="sanitizeHtml(bug.steps_to_reproduce)" />
            <span v-else class="muted-dash">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="预期结果" :span="2">
            <div v-if="bug.expected_result" class="rich-content" v-html="sanitizeHtml(bug.expected_result)" />
            <span v-else class="muted-dash">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="实际结果" :span="2">
            <div v-if="bug.actual_result" class="rich-content" v-html="sanitizeHtml(bug.actual_result)" />
            <span v-else class="muted-dash">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="环境信息" :span="2">{{ bug.environment || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="bug.reject_reason" label="拒绝原因" :span="2">
            {{ bug.reject_reason }}
          </el-descriptions-item>
          <el-descriptions-item v-if="bug.fix_description" label="修复说明" :span="2">
            {{ bug.fix_description }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 附件 -->
    <SectionCard v-if="bug" title="附件">
      <!-- 已上传列表 -->
      <div v-if="attachments.length > 0" class="file-list">
        <div
          v-for="att in attachments"
          :key="att.id"
          class="file-row"
        >
          <div class="file-left">
            <el-icon class="file-icon"><Document /></el-icon>
            <span class="file-name">{{ att.file_name }}</span>
            <span class="file-size">{{ formatFileSize(att.file_size) }}</span>
          </div>
          <div class="row-actions">
            <el-button size="small" @click="downloadAttachment(att)">下载</el-button>
            <el-button size="small" type="danger" plain @click="handleDeleteAttachment(att)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-else class="empty-text">暂无附件</div>

      <!-- 上传区 -->
      <div class="upload-row">
        <input
          ref="fileInputRef"
          type="file"
          style="display:none"
          multiple
          @change="handleFileChange"
        />
        <el-button
          type="primary"
          plain
          size="small"
          :loading="uploading"
          @click="fileInputRef?.click()"
        >
          <el-icon style="margin-right:4px;"><Upload /></el-icon>
          上传附件
        </el-button>
        <span v-if="uploading" class="upload-hint">上传中…</span>
      </div>
    </SectionCard>

    <!-- 关联测试用例 -->
    <SectionCard v-if="bug && relatedCases.length > 0" title="关联测试用例">
      <div
        v-for="rc in relatedCases"
        :key="rc.case_id"
        class="file-row"
      >
        <div class="file-left">
          <el-tag
            :type="RUN_RESULT_TYPE[rc.result]"
            size="small"
          >{{ RUN_RESULT_LABEL[rc.result] }}</el-tag>
          <span class="case-title-text">{{ rc.title }}</span>
          <el-tag v-if="rc.version_name" type="info" size="small">{{ rc.version_name }}</el-tag>
        </div>
        <div class="row-actions">
          <span class="executor-text">{{ rc.executor_name }}</span>
          <el-button size="small" plain @click="$router.push('/testcases')">查看用例</el-button>
        </div>
      </div>
    </SectionCard>

    <el-row :gutter="16">
      <!-- 操作历史 -->
      <el-col :span="12">
        <SectionCard title="操作历史">
          <el-timeline>
            <el-timeline-item
              v-for="h in history"
              :key="h.id"
              :timestamp="h.created_at?.slice(0,19).replace('T',' ')"
              placement="top"
            >
              <div class="history-line">
                <span class="history-user">{{ h.user_name }}</span>
                将 <code class="field-badge">{{ FIELD_LABELS[h.field_name] || h.field_name }}</code>
                从 <el-tag size="small" type="info">{{ formatValue(h.field_name, h.old_value) }}</el-tag>
                改为 <el-tag size="small" type="primary">{{ formatValue(h.field_name, h.new_value) }}</el-tag>
              </div>
              <div v-if="h.comment" class="history-note">
                备注：{{ h.comment }}
              </div>
            </el-timeline-item>
          </el-timeline>
        </SectionCard>
      </el-col>

      <!-- 评论 -->
      <el-col :span="12">
        <SectionCard title="评论">
          <div v-for="c in comments" :key="c.id" class="comment-item">
            <div class="comment-header">
              <span class="comment-author">{{ c.user_name }}</span>
              <span class="comment-time">{{ c.created_at?.slice(0,19).replace('T',' ') }}</span>
            </div>
            <div class="comment-body">{{ c.content }}</div>
          </div>
          <div v-if="comments.length === 0" class="empty-text centered">暂无评论</div>

          <!-- 发表评论 -->
          <div class="comment-input">
            <el-input v-model="newComment" type="textarea" :rows="3"
              placeholder="发表评论..." style="margin-bottom:8px;" />
            <el-button type="primary" size="small" :loading="commentLoading"
              @click="submitComment">发表评论</el-button>
          </div>
        </SectionCard>
      </el-col>
    </el-row>

    <!-- 状态流转对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="transitionForm" label-width="100px">
        <el-form-item v-if="currentAction === 'assign' || currentAction === 'reassign'" label="指派给">
          <el-select v-model="transitionForm.assignee_id" placeholder="请选择成员" style="width:100%">
            <el-option v-for="m in projectMembers" :key="m.user_id"
              :label="m.display_name" :value="m.user_id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="currentAction === 'reject'" label="拒绝原因">
          <el-input v-model="transitionForm.reject_reason" type="textarea" :rows="3"
            placeholder="请说明拒绝原因" />
        </el-form-item>
        <el-form-item v-if="currentAction === 'resolve'" label="修复说明">
          <el-input v-model="transitionForm.fix_description" type="textarea" :rows="3"
            placeholder="请描述修复内容" />
        </el-form-item>
        <el-form-item v-if="currentAction === 'reopen'" label="Reopen 原因">
          <el-input v-model="transitionForm.reopen_reason" type="textarea" :rows="3"
            placeholder="请说明重新打开的原因" />
        </el-form-item>
        <el-form-item label="备注（可选）">
          <el-input v-model="transitionForm.comment" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="transitioning" @click="confirmTransition">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Upload } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/project'
import { bugApi, projectApi, versionApi, testCaseApi } from '@/api'
import { getAvailableActions } from '@/utils/permission'
import { BUG_STATUS_MAP as STATUS_MAP } from '@/utils/status'
import { sanitizeHtml } from '@/utils/sanitize'
import StatusTag from '@/components/StatusTag.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import PriorityTag from '@/components/PriorityTag.vue'
import SectionCard from '@/components/SectionCard.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const projectStore = useProjectStore()

const bug = ref<any>(null)
const history = ref<any[]>([])
const comments = ref<any[]>([])
const projectMembers = ref<any[]>([])
const versions = ref<any[]>([])
const attachments = ref<any[]>([])
const relatedCases = ref<any[]>([])
const newComment = ref('')
const commentLoading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('')
const currentAction = ref('')
const transitioning = ref(false)
const transitionForm = reactive<any>({})

const RUN_RESULT_LABEL: Record<string, string> = {
  passed: '通过', failed: '失败', blocked: '阻塞', skipped: '跳过',
}
const RUN_RESULT_TYPE: Record<string, string> = {
  passed: 'success', failed: 'danger', blocked: 'warning', skipped: 'info',
}
const effectiveRole = ref('viewer')
const fileInputRef = ref<HTMLInputElement>()
const uploading = ref(false)

// 版本 ID → 名称映射
function versionName(id: number | null) {
  if (!id) return '—'
  const v = versions.value.find((v: any) => v.id === id)
  return v ? v.name : `#${id}`
}

function formatFileSize(bytes: number | null) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const FIELD_LABELS: Record<string, string> = {
  status: '状态', assignee_id: '指派人', priority: '优先级',
  severity: '严重度', reject_reason: '拒绝原因', fix_description: '修复说明',
  reopen_reason: 'Reopen原因', fixed_in_version_id: '修复版本',
}

const ACTION_STATUS_MAP: Record<string, string> = {
  assign: 'assigned', reassign: 'assigned', start: 'in_progress',
  resolve: 'resolved', close: 'closed', reject: 'rejected', reopen: 'reopened',
}

const ACTION_TITLE_MAP: Record<string, string> = {
  assign: '指派 Bug', reassign: '重新指派', start: '开始处理',
  resolve: '标记已修复', close: '关闭 Bug', reject: '拒绝 Bug', reopen: 'Reopen Bug',
}

function formatValue(field: string, val: string | null) {
  if (!val || val === 'None') return '空'
  if (field === 'status') return STATUS_MAP[val]?.label || val
  if (field === 'assignee_id') {
    const member = projectMembers.value.find((m: any) => String(m.user_id) === String(val))
    return member ? member.display_name : `用户#${val}`
  }
  return val
}

const availableActions = computed(() => {
  if (!bug.value) return []
  return getAvailableActions(
    bug.value.status,
    bug.value.assignee_id,
    auth.user?.id,
    effectiveRole.value,
    bug.value.reporter_id,
  )
})

async function load() {
  const id = Number(route.params.id)
  if (!id || isNaN(id)) {
    ElMessage.error('无效的 Bug ID')
    return
  }
  try {
    const [b, h, c, atts] = await Promise.all([
      bugApi.get(id) as any,
      bugApi.history(id) as any,
      bugApi.listComments(id) as any,
      bugApi.listAttachments(id) as any,
    ])
    bug.value = b
    history.value = h
    comments.value = c
    attachments.value = atts

    const pid = b.project_id
    const [members, vlist] = await Promise.all([
      projectApi.listMembers(pid) as any[],
      versionApi.list(pid) as any[],
    ])
    projectMembers.value = members
    versions.value = vlist
    const me = members.find((m: any) => m.user_id === auth.user?.id)
    effectiveRole.value = auth.user?.is_super_admin ? 'pm' : (me?.effective_role || 'viewer')

    // 加载关联测试用例
    try {
      relatedCases.value = await testCaseApi.relatedCases(id) as any[]
    } catch {}
  } catch {
    ElMessage.error('加载失败')
  }
}

onMounted(load)

async function submitComment() {
  if (!newComment.value.trim()) return
  commentLoading.value = true
  try {
    const c = await bugApi.addComment(bug.value.id, newComment.value) as any
    comments.value.push({ ...c, user_name: auth.user?.display_name })
    newComment.value = ''
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '评论失败')
  } finally {
    commentLoading.value = false
  }
}

function handleAction(action: string) {
  currentAction.value = action
  dialogTitle.value = ACTION_TITLE_MAP[action] || action
  Object.keys(transitionForm).forEach(k => delete transitionForm[k])
  if (action === 'start') { doTransition('in_progress', {}); return }
  if (action === 'close') { doTransition('closed', {}); return }
  dialogVisible.value = true
}

async function confirmTransition() {
  const toStatus = ACTION_STATUS_MAP[currentAction.value]
  if (!toStatus) return
  await doTransition(toStatus, { ...transitionForm })
  dialogVisible.value = false
}

async function doTransition(toStatus: string, extra: any) {
  transitioning.value = true
  try {
    const updated = await bugApi.transition(bug.value.id, { to_status: toStatus, ...extra }) as any
    bug.value = updated
    history.value = await bugApi.history(bug.value.id) as any[]
    ElMessage.success('操作成功')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '操作失败')
  } finally {
    transitioning.value = false
  }
}

// ── 附件上传 ──────────────────────────────────────────────
async function handleFileChange(event: Event) {
  const files = (event.target as HTMLInputElement).files
  if (!files || files.length === 0) return
  if (!bug.value?.id) { ElMessage.error('Bug 数据未加载，无法上传'); return }
  uploading.value = true
  try {
    for (const file of Array.from(files)) {
      // 1. 获取预签名 PUT URL
      const presign = await bugApi.presignUpload(bug.value.id, {
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      }) as any

      // 2. 直传 MinIO（不带 Authorization header）
      const putRes = await fetch(presign.upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
      })
      if (!putRes.ok) throw new Error(`上传失败: ${putRes.status}`)

      // 3. 通知后端写数据库
      const att = await bugApi.confirmUpload(bug.value.id, {
        object_key: presign.object_key,
        file_name: file.name,
        file_size: file.size,
        content_type: file.type || 'application/octet-stream',
      }) as any
      attachments.value.push(att)
    }
    ElMessage.success('附件上传成功')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '上传失败')
  } finally {
    uploading.value = false
    // 清空 input，允许重复选同一个文件
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
}

async function downloadAttachment(att: any) {
  const url = bugApi.downloadUrl(bug.value.id, att.id)
  try {
    // 用 fetch + Authorization header 下载（后端 OAuth2PasswordBearer 只认 header，不认 query）
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
    if (!res.ok) {
      ElMessage.error('下载失败，请重试')
      return
    }
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = att.file_name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(objectUrl)
  } catch {
    ElMessage.error('下载失败，请重试')
  }
}

async function handleDeleteAttachment(att: any) {
  try {
    await ElMessageBox.confirm(`确认删除附件「${att.file_name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await bugApi.deleteAttachment(bug.value.id, att.id)
    attachments.value = attachments.value.filter((a: any) => a.id !== att.id)
    ElMessage.success('附件已删除')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '删除失败')
  }
}

// 删除 Bug：仅超级管理员可见
const canDeleteBug = computed(() => !!auth.user?.is_super_admin)

async function deleteBug() {
  try {
    await ElMessageBox.confirm(
      `确认删除 Bug「${bug.value.title}」？此操作不可恢复。`,
      '删除 Bug',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return
  }
  try {
    await bugApi.delete(bug.value.id)
    ElMessage.success('Bug 已删除')
    router.back()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '删除失败')
  }
}
</script>

<style scoped>
/* ── Page Layout ──────────────────────────────────────────── */
.bug-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Bug Header Card ──────────────────────────────────────── */
.bug-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm, 6px);
  overflow: hidden;
}

.bug-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
  gap: 16px;
}

.bug-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.bug-id {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.bug-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.bug-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.bug-body {
  padding: 16px 20px;
}

/* ── File / Case Rows ─────────────────────────────────────── */
.file-list {
  margin-bottom: 12px;
}

.file-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
}

.file-row:last-child {
  border-bottom: none;
}

.file-left {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  min-width: 0;
}

.file-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.file-name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 8px;
}

.case-title-text {
  font-size: 13px;
  color: var(--text-primary);
}

.executor-text {
  font-size: 12px;
  color: var(--text-muted);
}

/* ── Upload Row ───────────────────────────────────────────── */
.upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 10px;
}

.upload-hint {
  font-size: 12px;
  color: var(--accent-violet, #7c3aed);
}

/* ── Empty State ──────────────────────────────────────────── */
.empty-text {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.empty-text.centered {
  text-align: center;
  padding: 20px 0;
  margin-bottom: 0;
}

/* ── History Timeline ─────────────────────────────────────── */
.history-line {
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.history-user {
  font-weight: 600;
  color: var(--text-primary);
}

.field-badge {
  background: var(--bg-canvas);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 2px 6px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-lime);
}

.history-note {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 4px;
}

/* ── Comments ─────────────────────────────────────────────── */
.comment-item {
  padding: 14px 0;
  border-bottom: 1px solid var(--border-subtle);
}

.comment-item:last-of-type {
  border-bottom: none;
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.comment-author {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.comment-time {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.comment-body {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  line-height: 1.6;
}

.comment-input {
  margin-top: 16px;
  border-top: 1px solid var(--border-subtle);
  padding-top: 16px;
}

/* ── Helpers ──────────────────────────────────────────────── */
.muted-dash {
  color: var(--text-muted);
}

/* ── Rich Content ─────────────────────────────────────────── */
.rich-content {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  word-break: break-word;
}

.rich-content :deep(p) { margin: 0 0 4px; }
.rich-content :deep(p:last-child) { margin-bottom: 0; }
.rich-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  border: 1px solid var(--border-subtle);
  margin: 4px 0;
  display: block;
}
.rich-content :deep(ul),
.rich-content :deep(ol) { padding-left: 20px; margin: 4px 0; }
.rich-content :deep(code) {
  background: var(--bg-canvas);
  border-radius: 3px;
  padding: 1px 4px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-lime);
}
.rich-content :deep(strong) { font-weight: 600; }
</style>
