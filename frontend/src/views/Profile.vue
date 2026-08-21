<template>
  <div class="profile-page">
    <div class="page-header">
      <el-avatar size="64" class="page-avatar">{{ auth.user?.display_name?.charAt(0) }}</el-avatar>
      <div>
        <div class="page-name">{{ auth.user?.display_name }}</div>
        <div class="page-email">{{ auth.user?.email }}</div>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- 修改密码 -->
      <el-col :span="12">
        <el-card>
          <template #header><span class="card-title">修改密码</span></template>
          <el-form :model="pwdForm" :rules="pwdRules" ref="pwdFormRef" label-width="90px">
            <el-form-item label="当前密码" prop="old_password">
              <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="输入当前密码" />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少 6 位" />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwdLoading" @click="submitPassword">保存密码</el-button>
              <el-button @click="resetPwdForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 邮件通知偏好 -->
      <el-col :span="12">
        <el-card v-loading="prefsLoading">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span class="card-title">邮件通知偏好</span>
              <el-tag v-if="!emailEnabled" type="warning" size="small">邮件服务未启用</el-tag>
            </div>
          </template>

          <div class="prefs-desc">选择你希望接收邮件通知的场景，关闭后系统将不再向你发送对应邮件。</div>

          <div class="pref-item">
            <div class="pref-info">
              <div class="pref-label">Bug 指派给我</div>
              <div class="pref-desc">当有 Bug 被指派给你时收到通知</div>
            </div>
            <el-switch v-model="prefs.email_notify_assigned" @change="savePrefs" />
          </div>
          <div class="pref-item">
            <div class="pref-info">
              <div class="pref-label">我的 Bug 状态变更</div>
              <div class="pref-desc">当你提交的 Bug 状态发生变化时收到通知</div>
            </div>
            <el-switch v-model="prefs.email_notify_status_changed" @change="savePrefs" />
          </div>
          <div class="pref-item">
            <div class="pref-info">
              <div class="pref-label">Bug 收到评论</div>
              <div class="pref-desc">当你提交或被指派的 Bug 有新评论时收到通知</div>
            </div>
            <el-switch v-model="prefs.email_notify_commented" @change="savePrefs" />
          </div>
          <div class="pref-item" style="border-bottom:none;">
            <div class="pref-info">
              <div class="pref-label">评论中提到我</div>
              <div class="pref-desc">当评论中 @ 了你的名字时收到通知</div>
            </div>
            <el-switch v-model="prefs.email_notify_mentioned" @change="savePrefs" />
          </div>

          <div style="margin-top:16px;display:flex;gap:8px;">
            <el-button size="small" text @click="setAll(true)">全部开启</el-button>
            <el-button size="small" text @click="setAll(false)">全部关闭</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { authApi, userApi } from '@/api'

const auth = useAuthStore()

// ── 修改密码 ──────────────────────────────────────────────────────
const pwdFormRef = ref()
const pwdLoading = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

const pwdRules = {
  old_password:     [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password:     [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_: any, val: string, cb: Function) => {
        val !== pwdForm.new_password ? cb(new Error('两次密码不一致')) : cb()
      },
      trigger: 'blur',
    },
  ],
}

function resetPwdForm() {
  pwdFormRef.value?.resetFields()
}

async function submitPassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return
  pwdLoading.value = true
  try {
    await authApi.changePassword(pwdForm.old_password, pwdForm.new_password)
    ElMessage.success('密码修改成功，下次登录请使用新密码')
    resetPwdForm()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '修改失败，请检查当前密码是否正确')
  } finally {
    pwdLoading.value = false
  }
}

// ── 邮件通知偏好 ──────────────────────────────────────────────────
const prefsLoading = ref(false)
const emailEnabled = ref(false)   // 服务端是否开启邮件（仅展示提示，不影响开关）
const prefs = reactive({
  email_notify_assigned:       true,
  email_notify_status_changed: true,
  email_notify_commented:      true,
  email_notify_mentioned:      true,
})

async function loadPrefs() {
  prefsLoading.value = true
  try {
    const res = await userApi.getNotifyPrefs() as any
    Object.assign(prefs, res)
  } catch {}
  prefsLoading.value = false
}

async function savePrefs() {
  try {
    await userApi.updateNotifyPrefs({ ...prefs })
    ElMessage.success('偏好已保存')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '保存失败')
  }
}

async function setAll(val: boolean) {
  prefs.email_notify_assigned       = val
  prefs.email_notify_status_changed = val
  prefs.email_notify_commented      = val
  prefs.email_notify_mentioned      = val
  await savePrefs()
}

onMounted(loadPrefs)
</script>

<style scoped>
.profile-page {
  max-width: 900px;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}
.page-avatar {
  background: #7c3aed;
  font-size: 24px;
  font-weight: 700;
  flex-shrink: 0;
}
.page-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary, #1d2129);
}
.page-email {
  font-size: 13px;
  color: var(--text-secondary, #909399);
  margin-top: 2px;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
}
.prefs-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
  line-height: 1.6;
}
.pref-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.pref-info { flex: 1; }
.pref-label {
  font-size: 14px;
  color: var(--text-primary, #1d2129);
  font-weight: 500;
}
.pref-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
