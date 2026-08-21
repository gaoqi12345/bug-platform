<template>
  <div
    class="stat-card"
    :class="`stat-card--${tone}`"
    :style="{ cursor: clickable ? 'pointer' : 'default' }"
    @click="clickable && emit('click')"
  >
    <div class="stat-card__icon">
      <el-icon size="28"><component :is="icon" /></el-icon>
    </div>
    <div class="stat-card__body">
      <div class="stat-card__value">{{ value }}</div>
      <div class="stat-card__label">{{ label }}</div>
    </div>
    <div v-if="clickable" class="stat-card__arrow">→</div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

withDefaults(defineProps<{
  tone: 'blue' | 'orange' | 'green' | 'purple'
  icon: Component
  value: number | string
  label: string
  clickable?: boolean
}>(), {
  clickable: true,
})

const emit = defineEmits<{ click: [] }>()
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-left-width: 4px;
  border-radius: 12px;
  transition: transform 0.15s, box-shadow 0.15s;
  position: relative;
  overflow: hidden;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.stat-card--blue   { border-left-color: var(--accent-violet); }
.stat-card--orange { border-left-color: var(--color-warning); }
.stat-card--green  { border-left-color: var(--color-success); }
.stat-card--purple { border-left-color: var(--accent-pink); }

.stat-card--blue   .stat-card__value,
.stat-card--blue   .stat-card__icon { color: var(--accent-violet); }
.stat-card--orange .stat-card__value,
.stat-card--orange .stat-card__icon { color: var(--color-warning); }
.stat-card--green  .stat-card__value,
.stat-card--green  .stat-card__icon { color: var(--color-success); }
.stat-card--purple .stat-card__value,
.stat-card--purple .stat-card__icon { color: var(--accent-pink); }

.stat-card__icon {
  flex-shrink: 0;
}

.stat-card__body {
  flex: 1;
}

.stat-card__value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
}

.stat-card__label {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 3px;
}

.stat-card__arrow {
  font-size: 16px;
  color: var(--text-muted);
  flex-shrink: 0;
}
</style>
