// Bug 状态显示配置
// type: Element Plus 语义类型（走 --el-color-* 自动适配主题）
// color: CSS 变量引用（用于 el-tag :color 直接指定背景色，随主题切换）
export const BUG_STATUS_MAP: Record<string, { label: string; type: string; color: string }> = {
  new:         { label: '新建',     type: 'info',    color: 'var(--color-info)' },
  assigned:    { label: '已指派',   type: 'primary',  color: 'var(--accent-lime)' },
  in_progress: { label: '处理中',   type: 'warning',  color: 'var(--color-warning)' },
  resolved:    { label: '待验证',   type: 'success',  color: 'var(--color-success)' },
  closed:      { label: '已关闭',   type: 'success',  color: 'var(--color-success)' },
  rejected:    { label: '已拒绝',   type: 'danger',   color: 'var(--color-danger)' },
  reopened:    { label: '重新打开', type: 'warning',  color: 'var(--color-warning)' },
}

// 严重度显示配置
export const SEVERITY_MAP: Record<string, { label: string; color: string }> = {
  critical: { label: 'Critical', color: 'var(--severity-critical)' },
  high:     { label: 'High',     color: 'var(--severity-high)' },
  medium:   { label: 'Medium',   color: 'var(--severity-medium)' },
  low:      { label: 'Low',      color: 'var(--severity-low)' },
}

// 优先级显示配置
export const PRIORITY_MAP: Record<string, { label: string; color: string }> = {
  p0: { label: 'P0', color: 'var(--priority-p0)' },
  p1: { label: 'P1', color: 'var(--priority-p1)' },
  p2: { label: 'P2', color: 'var(--priority-p2)' },
  p3: { label: 'P3', color: 'var(--priority-p3)' },
}

// 状态选项（用于筛选下拉）
export const STATUS_OPTIONS = Object.entries(BUG_STATUS_MAP).map(([value, { label }]) => ({ value, label }))
export const SEVERITY_OPTIONS = Object.entries(SEVERITY_MAP).map(([value, { label }]) => ({ value, label }))
export const PRIORITY_OPTIONS = Object.entries(PRIORITY_MAP).map(([value, { label }]) => ({ value, label }))
