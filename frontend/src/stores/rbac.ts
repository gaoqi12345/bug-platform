/**
 * rbac store — 权限点（Permission）与角色（Role）配置缓存
 *
 * 与 permissionConfig.ts（Bug 流转规则）是两个独立正交的系统：
 *   - rbac.ts：模块权限点（如 "bug.create"）与角色的绑定关系，控制"能否使用某功能"
 *   - permissionConfig.ts：Bug 状态流转规则，控制"哪些角色能触发哪个流转"
 *
 * Layout.vue 登录后预拉，RoleManagement.vue 修改角色后调用 reload() 刷新。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { rolesApi } from '@/api'

export interface PermissionDef {
  code: string
  module: string
  action: string
  label: string
  description: string | null
}

export interface RoleDef {
  id: number
  name: string
  label: string
  color: string
  description: string | null
  is_builtin: boolean
  sort_order: number
  permissions: string[]
}

export const useRbacStore = defineStore('rbac', () => {
  const permissions = ref<PermissionDef[]>([])
  const roles       = ref<RoleDef[]>([])
  const loaded      = ref(false)

  async function load() {
    try {
      const [perms, roleList] = await Promise.all([
        rolesApi.listPermissions() as any,
        rolesApi.listRoles()       as any,
      ])
      permissions.value = perms
      roles.value = roleList
      loaded.value = true
    } catch {
      // 静默失败，保持兜底空值
    }
  }

  /** 角色配置变更后调用，强制重新拉取 */
  async function reload() {
    loaded.value = false
    await load()
  }

  function getRole(name: string): RoleDef | undefined {
    return roles.value.find(r => r.name === name)
  }

  /** 判断某个角色名是否拥有指定权限点 */
  function roleHasPermission(roleName: string, permCode: string): boolean {
    const role = getRole(roleName)
    return role ? role.permissions.includes(permCode) : false
  }

  /** 按 module 分组的权限点目录，供 RoleManagement.vue 渲染分配矩阵使用 */
  const permissionsByModule = computed(() => {
    const groups: Record<string, PermissionDef[]> = {}
    for (const p of permissions.value) {
      if (!groups[p.module]) groups[p.module] = []
      groups[p.module].push(p)
    }
    return groups
  })

  return {
    permissions,
    roles,
    loaded,
    load,
    reload,
    getRole,
    roleHasPermission,
    permissionsByModule,
  }
})
