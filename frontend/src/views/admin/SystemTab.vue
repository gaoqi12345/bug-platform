<template>
  <el-card>
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>邮件通知配置</span>
        <el-tag :type="emailForm.email_enabled ? 'success' : 'info'" size="small">
          {{ emailForm.email_enabled ? '已启用' : '未启用' }}
        </el-tag>
      </div>
    </template>

    <div v-loading="emailLoading">
      <el-form :model="emailForm" label-width="130px" style="max-width:580px;">
        <el-form-item label="启用邮件通知">
          <el-switch v-model="emailForm.email_enabled" />
          <span style="font-size:12px;color:var(--text-secondary,#909399);margin-left:10px;">
            关闭后系统不发送任何邮件通知
          </span>
        </el-form-item>
        <el-divider />
        <el-form-item label="SMTP 服务器">
          <el-input v-model="emailForm.smtp_host" placeholder="如：smtp.exmail.qq.com" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="emailForm.smtp_port" :min="1" :max="65535" style="width:140px;" />
          <span style="font-size:12px;color:var(--text-secondary,#909399);margin-left:10px;">
            SSL 用 465，STARTTLS 用 587
          </span>
        </el-form-item>
        <el-form-item label="加密方式">
          <el-radio-group v-model="emailForm.smtp_use_ssl">
            <el-radio :value="true">SSL/TLS（端口 465）</el-radio>
            <el-radio :value="false">STARTTLS（端口 587）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="发件账号">
          <el-input v-model="emailForm.smtp_user" placeholder="noreply@yourcompany.com" />
        </el-form-item>
        <el-form-item label="密码 / 授权码">
          <el-input
            v-model="emailForm.smtp_password"
            type="password"
            show-password
            :placeholder="emailForm.has_password ? '已设置（留空保留原密码）' : '请输入邮箱密码或授权码'"
          />
        </el-form-item>
        <el-form-item label="发件人名称">
          <el-input v-model="emailForm.email_from_name" placeholder="Bug Platform" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="emailSaving" @click="saveEmailSettings">
            保存配置
          </el-button>
          <el-button @click="loadEmailSettings">重置</el-button>
        </el-form-item>
      </el-form>

      <el-divider content-position="left">连接测试</el-divider>
      <div style="display:flex;align-items:center;gap:10px;max-width:580px;padding-left:130px;">
        <el-input
          v-model="testEmailAddr"
          placeholder="输入收件邮箱地址"
          style="flex:1;"
          clearable
        />
        <el-button type="success" :loading="emailTesting" @click="sendTestEmail">
          发送测试邮件
        </el-button>
      </div>
      <div v-if="testEmailResult" style="margin-top:10px;padding-left:130px;">
        <el-alert
          :title="testEmailResult.message"
          :type="testEmailResult.ok ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
      </div>
    </div>
  </el-card>

  <!-- ══════════════ 飞书通知配置 ══════════════ -->
  <el-card style="margin-top:16px;">
    <template #header>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>飞书通知配置</span>
        <div>
          <el-tag v-if="feishuForm.group_notify_enabled" type="success" size="small">群通知已启用</el-tag>
          <el-tag v-else type="info" size="small">群通知未启用</el-tag>
          <el-tag
            v-if="feishuForm.private_notify_enabled"
            type="success" size="small" style="margin-left:6px;"
          >私聊通知已启用</el-tag>
          <el-tag
            v-else type="info" size="small" style="margin-left:6px;"
          >私聊通知未启用</el-tag>
        </div>
      </div>
    </template>

    <div v-loading="feishuLoading">
      <el-form :model="feishuForm" label-width="130px" style="max-width:580px;">
        <el-form-item label="群通知总开关">
          <el-switch v-model="feishuForm.group_notify_enabled" />
          <span style="font-size:12px;color:var(--text-secondary,#909399);margin-left:10px;">
            关闭后不再向群里推送 Bug 指派通知（webhook 机器人）
          </span>
        </el-form-item>
        <el-form-item label="私聊通知总开关">
          <el-switch v-model="feishuForm.private_notify_enabled" />
          <span style="font-size:12px;color:var(--text-secondary,#909399);margin-left:10px;">
            开启后 Bug 指派时向被指派人发送飞书个人消息（需配置下方自建应用）
          </span>
        </el-form-item>
        <el-divider />
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom:16px;"
          title="个人私聊 + 卡片交互按钮需要飞书自建应用"
          description="在飞书开放平台创建企业自建应用，开启机器人能力，申请 im:message 权限，并在「事件与回调 → 回调配置」订阅卡片回传交互（card.action.trigger），投递方式选「使用长连接接收回调」即可本地联调。"
        />
        <el-form-item label="App ID">
          <el-input v-model="feishuForm.app_id" placeholder="cli_xxxxxxxxxxxxxxxx" />
        </el-form-item>
        <el-form-item label="App Secret">
          <el-input
            v-model="feishuForm.app_secret"
            type="password"
            show-password
            :placeholder="feishuForm.has_app_secret ? '已设置（留空保留原值）' : '请输入应用密钥'"
          />
        </el-form-item>
        <el-form-item label="回调校验 Token">
          <el-input
            v-model="feishuForm.verification_token"
            :placeholder="feishuForm.has_verification_token ? '已设置（留空保留原值）' : '开发者后台加密策略的 Verification Token'"
          />
          <span style="font-size:12px;color:var(--text-secondary,#909399);">
            用于校验飞书卡片回调请求来源
          </span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="feishuSaving" @click="saveFeishuSettings">
            保存配置
          </el-button>
          <el-button @click="loadFeishuSettings">重置</el-button>
        </el-form-item>
      </el-form>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { systemApi } from '@/api'

const emailLoading   = ref(false)
const emailSaving    = ref(false)
const emailTesting   = ref(false)
const testEmailAddr  = ref('')
const testEmailResult = ref<{ ok: boolean; message: string } | null>(null)

const feishuLoading = ref(false)
const feishuSaving  = ref(false)

const feishuForm = reactive({
  group_notify_enabled:   true,
  private_notify_enabled: false,
  app_id:                 '',
  app_secret:             '',
  verification_token:     '',
  has_app_secret:         false,
  has_verification_token: false,
})

const emailForm = reactive({
  email_enabled:   false,
  smtp_host:       '',
  smtp_port:       465,
  smtp_user:       '',
  smtp_password:   '',
  smtp_use_ssl:    true,
  email_from_name: 'Bug Platform',
  has_password:    false,
})

async function loadEmailSettings() {
  emailLoading.value = true
  try {
    const res = await systemApi.getEmailSettings() as any
    Object.assign(emailForm, { ...res, smtp_password: '' })
  } catch (e: any) {
    ElMessage.error('加载邮件配置失败')
  } finally {
    emailLoading.value = false
  }
}

async function saveEmailSettings() {
  emailSaving.value = true
  try {
    await systemApi.updateEmailSettings({ ...emailForm })
    ElMessage.success('邮件配置已保存')
    await loadEmailSettings()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '保存失败')
  } finally {
    emailSaving.value = false
  }
}

async function sendTestEmail() {
  if (!testEmailAddr.value) { ElMessage.warning('请输入收件邮箱地址'); return }
  emailTesting.value  = true
  testEmailResult.value = null
  try {
    const res = await systemApi.testEmail(testEmailAddr.value) as any
    testEmailResult.value = { ok: true, message: res.message || `测试邮件已发送至 ${testEmailAddr.value}` }
  } catch (e: any) {
    testEmailResult.value = { ok: false, message: typeof e === 'string' ? e : 'SMTP 连接失败，请检查配置' }
  } finally {
    emailTesting.value = false
  }
}

async function loadFeishuSettings() {
  feishuLoading.value = true
  try {
    const res = await systemApi.getFeishuSettings() as any
    Object.assign(feishuForm, { ...res, app_secret: '', verification_token: '' })
  } catch (e: any) {
    ElMessage.error('加载飞书配置失败')
  } finally {
    feishuLoading.value = false
  }
}

onMounted(() => {
  loadEmailSettings()
  loadFeishuSettings()
})

async function saveFeishuSettings() {
  feishuSaving.value = true
  try {
    await systemApi.updateFeishuSettings({ ...feishuForm })
    ElMessage.success('飞书配置已保存')
    await loadFeishuSettings()
  } catch (e: any) {
    ElMessage.error(typeof e === 'string' ? e : '保存失败')
  } finally {
    feishuSaving.value = false
  }
}
</script>
