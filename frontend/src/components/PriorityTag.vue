<template>
  <el-tag :color="conf.color" effect="dark" :size="size" style="border:none">{{ conf.label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PRIORITY_MAP } from '@/utils/status'

const props = withDefaults(defineProps<{
  priority: string
  size?: 'large' | 'default' | 'small'
}>(), {
  size: 'small',
})

const conf = computed(() =>
  PRIORITY_MAP[props.priority] || { label: props.priority, color: 'var(--text-muted)' }
)
</script>
