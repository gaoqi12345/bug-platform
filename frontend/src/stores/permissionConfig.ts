/**
 * permissionConfig store — Bug 状态流转规则缓存
 *
 * 与 rbac.ts（模块权限点/角色）是两个独立正交的系统：
 *   - permissionConfig.ts：Bug 状态流转规则（transition_rules 表），控制"哪些角色能触发哪个流转"
 *   - rbac.ts：模块权限点与角色绑定（permissions/roles/role_permissions 表），控制"能否使用某功能"
 *
 * Layout.vue 登录后预拉，Admin.vue 修改规则后调用 reload() 刷新。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { configApi } from '@/api'

export interface TransitionRule {
  from_status:     string
  to_status:       string
  allowed_roles:   string[]
  required_fields: string[]
  condition_type:  string | null
  condition_msg:   string | null
  is_enabled:      boolean
}

export const usePermissionConfigStore = defineStore('permissionConfig', () => {
  const transitionRules = ref<TransitionRule[]>([])
  const loaded           = ref(false)

  async function load() {
    try {
      transitionRules.value = await configApi.listTransitionRules() as any
      loaded.value = true
    } catch {
      // 静默失败，保持兜底值
    }
  }

  /** 修改规则后调用，强制重新拉取 */
  async function reload() {
    loaded.value = false
    await load()
  }

  /**
   * 获取指定 from→to 流转规则，找不到返回 null
   */
  function getRule(fromStatus: string, toStatus: string): TransitionRule | null {
    return transitionRules.value.find(
      r => r.from_status === fromStatus && r.to_status === toStatus
    ) ?? null
  }

  return {
    transitionRules,
    loaded,
    load,
    reload,
    getRule,
  }
})
