<template>
  <el-tag :color="conf.color" effect="dark" :size="size" style="border:none">{{ conf.label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SEVERITY_MAP } from '@/utils/status'

const props = withDefaults(defineProps<{
  severity: string
  size?: 'large' | 'default' | 'small'
}>(), {
  size: 'small',
})

const conf = computed(() =>
  SEVERITY_MAP[props.severity] || { label: props.severity, color: 'var(--text-muted)' }
)
</script>
