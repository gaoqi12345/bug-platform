<template>
  <div class="login-bg">
    <div class="login-center">
      <div class="login-card">
        <!-- Logo -->
        <div class="login-logo">
          <span class="logo-bug">🐛</span>
          <h1 class="logo-title">缺陷管理平台</h1>
          <p class="logo-sub">Bug Management Platform</p>
        </div>

        <!-- Form -->
        <el-form :model="form" :rules="rules" ref="formRef" @keyup.enter="handleLogin" class="login-form">
          <el-form-item prop="email">
            <el-input
              v-model="form.email"
              placeholder="邮箱"
              :prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              :prefix-icon="Lock"
              size="large"
              show-password
            />
          </el-form-item>
          <el-form-item class="form-item-submit">
            <button
              class="submit-btn"
              :disabled="loading"
              @click="handleLogin"
              type="button"
            >
              <span v-if="!loading">登录</span>
              <span v-else class="btn-loading">
                <svg class="spin-icon" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
                </svg>
                登录中…
              </span>
            </button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({ email: '', password: '' })
const rules = {
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login(form.email, form.password)
    router.push('/')
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '登录失败，请检查邮箱和密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ── 登录页 — 跟随主题（Linear 极简）────────────────────────── */
.login-bg {
  min-height: 100vh;
  background: var(--bg-canvas);
  position: relative;
  overflow: hidden;
  transition: background 0.2s ease;
}

/* Center wrapper */
.login-center {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
}

/* Card */
.login-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  padding: 48px 40px;
  width: 420px;
  box-shadow: var(--shadow-lg);
}

/* Logo block */
.login-logo {
  text-align: center;
  margin-bottom: 36px;
}

.logo-bug {
  display: block;
  font-size: 48px;
  line-height: 1;
  margin-bottom: 12px;
}

.logo-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.logo-sub {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

/* Form overrides */
.login-form :deep(.el-form-item__error) {
  color: var(--color-danger);
}

.login-form :deep(.el-input__wrapper) {
  background: var(--bg-input) !important;
  box-shadow: 0 0 0 1px var(--border-input) !important;
  border-radius: var(--radius-md);
  transition: box-shadow 0.2s ease;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  background: var(--bg-input) !important;
  box-shadow: 0 0 0 1px var(--border-focus) !important;
}

.login-form :deep(.el-input__inner) {
  color: var(--text-primary) !important;
  -webkit-text-fill-color: var(--text-primary) !important;
  background: transparent !important;
  background-color: transparent !important;
}

/* 覆盖浏览器 autofill 注入的背景 */
.login-form :deep(.el-input__inner:-webkit-autofill),
.login-form :deep(.el-input__inner:-webkit-autofill:hover),
.login-form :deep(.el-input__inner:-webkit-autofill:focus),
.login-form :deep(.el-input__inner:-webkit-autofill:active) {
  -webkit-box-shadow: 0 0 0px 1000px var(--bg-input) inset !important;
  box-shadow:         0 0 0px 1000px var(--bg-input) inset !important;
  -webkit-text-fill-color: var(--text-primary) !important;
  caret-color: var(--text-primary);
  transition: background-color 5000s ease-in-out 0s;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: var(--text-muted);
  -webkit-text-fill-color: var(--text-muted);
}

.login-form :deep(.el-input__prefix-inner .el-icon) {
  color: var(--accent-lime);
}

/* Password show/hide icon */
.login-form :deep(.el-input__suffix-inner .el-icon) {
  color: var(--text-muted);
}

/* el-form-item spacing */
.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.form-item-submit {
  margin-top: 8px;
  margin-bottom: 0 !important;
}

.form-item-submit :deep(.el-form-item__content) {
  display: block;
}

/* Submit button */
.submit-btn {
  background: var(--accent-lime);
  color: var(--text-inverse);
  font-weight: 600;
  width: 100%;
  height: 44px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 15px;
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: opacity 0.18s ease, transform 0.12s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.88;
}

.submit-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Loading spinner */
.btn-loading {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spin-icon {
  width: 16px;
  height: 16px;
  animation: spin 0.8s linear infinite;
  color: var(--text-inverse);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
