<template>
  <div class="section-card">
    <div class="section-title">{{ title }}</div>
    <div class="section-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<style scoped>
.section-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm, 6px);
  overflow: hidden;
}

.section-title {
  padding: 10px 16px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-surface-2);
}

.section-body {
  padding: 14px 16px;
}
</style>
