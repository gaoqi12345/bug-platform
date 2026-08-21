import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeMode = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
  const STORAGE_KEY = 'bug-platform-theme'

  // 初始值：读 localStorage，没有则默认 dark（Sentry 风格以深色为主）
  const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
  const mode = ref<ThemeMode>(saved === 'light' ? 'light' : 'dark')

  function apply(m: ThemeMode) {
    document.documentElement.setAttribute('data-theme', m)
  }

  function toggle() {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  function setMode(m: ThemeMode) {
    mode.value = m
  }

  // 响应式：mode 变化时同步 DOM + localStorage
  watch(mode, (m) => {
    apply(m)
    localStorage.setItem(STORAGE_KEY, m)
  }, { immediate: true })

  return { mode, toggle, setMode }
})
