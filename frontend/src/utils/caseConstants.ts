// 测试用例模块共享常量
// 注意：用例优先级存大写字符串（P0/P1/P2/P3），与 bugs.priority 的小写枚举不同

export const CASE_PRIORITY_OPTIONS = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
]

export const CASE_PRIORITY_STYLE: Record<string, Record<string, string>> = {
  P0: { background: 'var(--color-danger-bg)', color: 'var(--color-danger)', border: '1px solid var(--color-danger)' },
  P1: { background: 'var(--color-warning-bg)', color: 'var(--color-warning)', border: '1px solid var(--color-warning)' },
  P2: { background: 'var(--color-info-bg)', color: 'var(--color-info)', border: '1px solid var(--color-info)' },
  P3: { background: 'var(--color-info-bg)', color: 'var(--color-info)', border: '1px solid var(--color-info)' },
}

export const RUN_RESULT_LABEL: Record<string, string> = {
  passed: '通过', failed: '失败', blocked: '阻塞', skipped: '跳过',
}

export const RUN_RESULT_TYPE: Record<string, string> = {
  passed: 'success', failed: 'danger', blocked: 'warning', skipped: 'info',
}
