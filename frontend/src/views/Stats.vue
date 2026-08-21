<template>
  <div>
    <el-row :gutter="16" style="margin-bottom:16px;">
      <el-col :span="12">
        <el-card header="Bug 状态概览">
          <div ref="pieChart" style="height:300px;" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="Bug 创建趋势（近14天）">
          <div ref="lineChart" style="height:300px;" />
        </el-card>
      </el-col>
    </el-row>

    <el-card header="版本 Bug 分布报表">
      <el-form inline style="margin-bottom:12px;">
        <el-form-item label="选择版本">
          <el-select v-model="selectedVersionId" placeholder="请选择版本" style="width:200px">
            <el-option v-for="v in versions" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadVersionReport">查询</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="versionReport" stripe>
        <el-table-column prop="severity" label="严重度" width="120">
          <template #default="{ row }">
            <SeverityTag :severity="row.severity?.toLowerCase()" />
          </template>
        </el-table-column>
        <el-table-column prop="total" label="总数" width="80" />
        <el-table-column prop="new_count" label="新建" width="80" />
        <el-table-column prop="assigned_count" label="已指派" width="80" />
        <el-table-column prop="in_progress_count" label="处理中" width="80" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useProjectStore, ALL_PROJECTS } from '@/stores/project'
import { useThemeStore } from '@/stores/theme'
import { statsApi, versionApi } from '@/api'
import { BUG_STATUS_MAP as STATUS_MAP } from '@/utils/status'
import SeverityTag from '@/components/SeverityTag.vue'

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const pieChart = ref<HTMLElement>()
const lineChart = ref<HTMLElement>()
const versions = ref<any[]>([])
const selectedVersionId = ref<number>()
const versionReport = ref<any[]>([])

let pieInstance: echarts.ECharts | null = null
let lineInstance: echarts.ECharts | null = null

// ── 从 CSS 变量读取实际颜色（ECharts 是 canvas，不支持 CSS var）──
function cssVar(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

// 解析 status.ts 里的 'var(--xxx)' 为实际 hex/rgb
function resolveColor(colorStr: string): string {
  const m = colorStr?.match(/var\((--[\w-]+)\)/)
  if (m) return cssVar(m[1], '#8c959f')
  return colorStr || '#8c959f'
}

// 图表主题色（随 data-theme 切换）
function chartColors() {
  return {
    text:      cssVar('--text-secondary', '#9ba1a6'),
    muted:     cssVar('--text-muted', '#6e7681'),
    border:    cssVar('--border-subtle', '#26292f'),
    accent:    cssVar('--accent-lime', '#5e6ad2'),
    accentBg:  cssVar('--accent-lime-bg', 'rgba(94,106,210,0.14)'),
  }
}

async function loadCharts() {
  const pid = projectStore.currentProjectId
  if (!pid) return
  try {
    // 「全部项目」模式不传 project_id，后端按用户所属项目统计
    const [ov, trend] = await Promise.all([
      pid === ALL_PROJECTS ? statsApi.overview() : statsApi.overview(pid) as any,
      pid === ALL_PROJECTS ? statsApi.trend() : statsApi.trend(pid, 14) as any[],
    ])

    const c = chartColors()

    // 饼图
    const { total, ...statusData } = ov
    await nextTick()
    if (pieChart.value) {
      if (!pieInstance) pieInstance = echarts.init(pieChart.value)
      pieInstance.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)',
          textStyle: { color: c.text },
        },
        legend: {
          bottom: 0,
          textStyle: { color: c.text },
        },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: Object.entries(statusData)
            .filter(([, v]) => (v as number) > 0)
            .map(([k, v]) => ({
              name: STATUS_MAP[k]?.label || k,
              value: v,
              itemStyle: { color: resolveColor(STATUS_MAP[k]?.color || '') },
            })),
        }],
      })
    }

    // 折线图
    if (lineChart.value) {
      if (!lineInstance) lineInstance = echarts.init(lineChart.value)
      lineInstance.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          textStyle: { color: c.text },
        },
        xAxis: {
          type: 'category',
          data: (trend as any[]).map((d: any) => d.day),
          axisLine: { lineStyle: { color: c.border } },
          axisLabel: { color: c.text },
          splitLine: { lineStyle: { color: c.border } },
        },
        yAxis: {
          type: 'value',
          minInterval: 1,
          axisLine: { lineStyle: { color: c.border } },
          axisLabel: { color: c.text },
          splitLine: { lineStyle: { color: c.border } },
        },
        series: [{
          name: '新增 Bug',
          type: 'line',
          smooth: true,
          areaStyle: { color: c.accentBg },
          data: (trend as any[]).map((d: any) => d.count),
          itemStyle: { color: c.accent },
        }],
      })
    }
  } catch {}
}

async function loadVersionReport() {
  // 版本报表按版本聚合，「全部项目」模式（-1）无单项目版本，跳过
  if (!selectedVersionId.value || projectStore.currentProjectId <= 0) return
  try {
    versionReport.value = await statsApi.versionReport(
      projectStore.currentProjectId,
      selectedVersionId.value,
    ) as any[]
  } catch {}
}

async function loadVersions() {
  const pid = projectStore.currentProjectId
  // 「全部项目」模式无单一项目版本，跳过
  if (!pid || pid === ALL_PROJECTS) return
  try {
    versions.value = await versionApi.list(pid) as any[]
  } catch {}
}

onMounted(async () => {
  await loadVersions()
  await loadCharts()
})

watch(() => projectStore.currentProjectId, async () => {
  await loadVersions()
  await loadCharts()
})

// 主题切换时重绘图表（颜色取自 CSS 变量）
watch(() => themeStore.mode, async () => {
  await nextTick()
  await loadCharts()
})
</script>

<style scoped>
/* Page relies entirely on global CSS */
</style>
