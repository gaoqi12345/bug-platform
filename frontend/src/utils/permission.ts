/**
 * permission.ts — Bug 操作按钮可见性判断
 *
 * getAvailableActions() 从 permissionConfig store 读取流转规则（动态），
 * "是否拥有完全操作权限"改为查询 rbac store 的 bug.edit_any 权限点
 * （而非硬编码判断 role === 'pm'），以支持拥有该权限点的自定义角色。
 * 函数签名与原版完全一致，调用方无需改动。
 */
import { usePermissionConfigStore } from '@/stores/permissionConfig'
import { useRbacStore } from '@/stores/rbac'

/**
 * 通用权限点判断：role 是否拥有 permCode。
 * 供全局各处按钮/入口的可见性判断使用。
 */
export function hasPermission(role: string, permCode: string): boolean {
  try {
    return useRbacStore().roleHasPermission(role, permCode)
  } catch {
    return false
  }
}

/** 按钮定义 */
interface ActionDef {
  label:  string
  action: string
  type:   string
}

/**
 * 根据 Bug 状态 + 用户角色 + 身份，返回可显示的操作按钮列表。
 * 优先从 store 中的动态规则派生，store 未加载时使用静态兜底。
 */
export function getAvailableActions(
  bugStatus:     string,
  assigneeId:    number | null,
  currentUserId: number,
  effectiveRole: string,
  reporterId?:   number | null,
): ActionDef[] {
  const actions: ActionDef[] = []
  const isAssignee = assigneeId    === currentUserId
  const isReporter = reporterId    === currentUserId
  // "完全操作权限"：拥有 bug.edit_any 权限点的角色（含自定义角色），等效于旧系统里的 pm
  const hasFullAccess = hasPermission(effectiveRole, 'bug.edit_any')
  const canAssign  = hasFullAccess || isReporter   // 拥有完全权限可指派任意，reporter 可指派自己的

  // 尝试从 store 读流转规则
  let store: ReturnType<typeof usePermissionConfigStore> | null = null
  try {
    store = usePermissionConfigStore()
  } catch {
    // Pinia 未初始化（单元测试等场景），使用兜底
  }

  /**
   * 判断当前用户能否触发某条流转。
   * 从 store 读 allowed_roles + condition_type；store 无数据时使用传入的兜底 roles 列表。
   */
  function canTransit(toStatus: string, fallbackRoles: string[]): boolean {
    if (store?.loaded) {
      const rule = store.getRule(bugStatus, toStatus)
      if (!rule || !rule.is_enabled) return false
      if (!rule.allowed_roles.includes(effectiveRole)) return false
      // condition 检查（与后端 transitions.py 的 has_permission(bug.edit_any) 逻辑一致）
      if (rule.condition_type === 'reporter_or_pm')
        return hasFullAccess || isReporter
      if (rule.condition_type === 'assignee_only')
        return hasFullAccess || isAssignee
      return true
    }
    // 兜底：静态角色列表
    return fallbackRoles.includes(effectiveRole)
  }

  // ── 各状态按钮 ────────────────────────────────────────────────

  if (bugStatus === 'new') {
    if (canAssign && canTransit('assigned', ['pm', 'tester', 'developer']))
      actions.push({ label: '指派', action: 'assign', type: 'primary' })
    if (canTransit('rejected', ['pm', 'developer']))
      actions.push({ label: '拒绝', action: 'reject', type: 'danger' })
  }

  if (bugStatus === 'assigned') {
    if ((isAssignee || hasFullAccess) && canTransit('in_progress', ['developer', 'pm']))
      actions.push({ label: '开始处理', action: 'start', type: 'primary' })
    if (canAssign && canTransit('assigned', ['pm', 'tester', 'developer']))
      actions.push({ label: '重新指派', action: 'reassign', type: 'warning' })
    if (canTransit('rejected', ['pm', 'developer']))
      actions.push({ label: '拒绝', action: 'reject', type: 'danger' })
  }

  if (bugStatus === 'in_progress') {
    if ((isAssignee || hasFullAccess) && canTransit('resolved', ['developer', 'pm']))
      actions.push({ label: '标记已修复', action: 'resolve', type: 'success' })
    if (canAssign && canTransit('assigned', ['pm', 'tester', 'developer']))
      actions.push({ label: '重新指派', action: 'reassign', type: 'warning' })
    if (canTransit('rejected', ['pm', 'developer']))
      actions.push({ label: '拒绝', action: 'reject', type: 'danger' })
  }

  if (bugStatus === 'resolved') {
    if (canTransit('closed',   ['tester', 'pm']))
      actions.push({ label: '验证通过', action: 'close',  type: 'success' })
    if (canTransit('reopened', ['tester', 'pm']))
      actions.push({ label: '验证失败', action: 'reopen', type: 'warning' })
  }

  if (bugStatus === 'rejected' && canTransit('reopened', ['tester', 'pm']))
    actions.push({ label: 'Reopen', action: 'reopen', type: 'warning' })

  if (bugStatus === 'closed' && canTransit('reopened', ['tester', 'pm']))
    actions.push({ label: 'Reopen', action: 'reopen', type: 'warning' })

  if (bugStatus === 'reopened') {
    if (canAssign && canTransit('assigned', ['pm', 'tester', 'developer']))
      actions.push({ label: '重新指派', action: 'assign', type: 'primary' })
  }

  return actions
}
