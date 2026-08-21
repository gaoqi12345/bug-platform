import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 「全部项目」哨兵值（-1），与"未选择项目"(0) 区分
export const ALL_PROJECTS = -1

export const useProjectStore = defineStore('project', () => {
  const currentProjectId = ref<number>(
    Number(localStorage.getItem('currentProjectId') || 0)
  )
  const projects = ref<any[]>([])

  function setCurrentProject(id: number) {
    currentProjectId.value = id
    localStorage.setItem('currentProjectId', String(id))
  }

  // 当前项目是否已归档
  const isCurrentProjectArchived = computed(() => {
    const p = projects.value.find((p: any) => p.id === currentProjectId.value)
    return p?.status === 'archived'
  })

  // 当前项目对象
  const currentProject = computed(() =>
    projects.value.find((p: any) => p.id === currentProjectId.value) ?? null
  )

  return { currentProjectId, projects, setCurrentProject, isCurrentProjectArchived, currentProject }
})
