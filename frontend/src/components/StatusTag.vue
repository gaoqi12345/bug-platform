<template>
  <el-tag :type="conf.type" :size="size">{{ conf.label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BUG_STATUS_MAP } from '@/utils/status'

const props = withDefaults(defineProps<{
  status: string
  size?: 'large' | 'default' | 'small'
}>(), {
  size: 'small',
})

const conf = computed(() =>
  BUG_STATUS_MAP[props.status] || { label: props.status, type: 'info', color: '' }
)
</script>
