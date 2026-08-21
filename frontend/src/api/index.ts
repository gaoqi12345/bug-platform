import http from './http'

export const authApi = {
  login: (email: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    return http.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
  me: () => http.get('/auth/me'),
  changePassword: (oldPassword: string, newPassword: string) =>
    http.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword }),
}

export const userApi = {
  list: () => http.get('/users'),
  create: (data: any) => http.post('/users', data),
  importUsers: (users: any[]) => http.post('/users/import', { users }),
  update: (id: number, data: any) => http.put(`/users/${id}`, data),
  deactivate: (id: number) => http.delete(`/users/${id}`),
  activate: (id: number) => http.post(`/users/${id}/activate`, {}),
  getNotifyPrefs: () => http.get('/users/me/notify-prefs'),
  updateNotifyPrefs: (data: Record<string, boolean>) => http.put('/users/me/notify-prefs', data),
}

export const teamApi = {
  list: () => http.get('/teams'),
  create: (data: any) => http.post('/teams', data),
  update: (id: number, data: any) => http.put(`/teams/${id}`, data),
  delete: (id: number) => http.delete(`/teams/${id}`),
  listMembers: (teamId: number) => http.get(`/teams/${teamId}/members`),
  addMember: (teamId: number, data: any) => http.post(`/teams/${teamId}/members`, data),
  addMembers: (teamId: number, members: { user_id: number; role: string }[]) =>
    http.post(`/teams/${teamId}/members/batch`, { members }),
  updateMember: (teamId: number, userId: number, data: any) => http.put(`/teams/${teamId}/members/${userId}`, data),
  removeMember: (teamId: number, userId: number) => http.delete(`/teams/${teamId}/members/${userId}`),
}

export const projectApi = {
  list: (includeArchived = false) => http.get('/projects', { params: includeArchived ? { include_archived: true } : {} }),
  create: (data: any) => http.post('/projects', data),
  update: (id: number, data: any) => http.put(`/projects/${id}`, data),
  archive: (id: number) => http.delete(`/projects/${id}`),
  listMembers: (id: number) => http.get(`/projects/${id}/members`),
  overrideMember: (id: number, data: any) => http.post(`/projects/${id}/members`, data),
  removeMember: (id: number, userId: number) => http.delete(`/projects/${id}/members/${userId}`),
}

export const versionApi = {
  list: (projectId: number) => http.get(`/projects/${projectId}/versions`),
  create: (projectId: number, data: any) => http.post(`/projects/${projectId}/versions`, data),
  update: (projectId: number, versionId: number, data: any) => http.put(`/projects/${projectId}/versions/${versionId}`, data),
  delete: (projectId: number, versionId: number) => http.delete(`/projects/${projectId}/versions/${versionId}`),
  updateStatus: (projectId: number, versionId: number, status: string) =>
    http.patch(`/projects/${projectId}/versions/${versionId}/status`, { status }),
}

export const bugApi = {
  list: (params: any) => http.get('/bugs', { params }),
  get: (id: number) => http.get(`/bugs/${id}`),
  create: (projectId: number, data: any) => http.post(`/bugs?project_id=${projectId}`, data),
  update: (id: number, data: any) => http.put(`/bugs/${id}`, data),
  delete: (id: number) => http.delete(`/bugs/${id}`),
  transition: (id: number, data: any) => http.patch(`/bugs/${id}/transition`, data),
  history: (id: number) => http.get(`/bugs/${id}/history`),
  listComments: (id: number) => http.get(`/bugs/${id}/comments`),
  addComment: (id: number, content: string) => http.post(`/bugs/${id}/comments`, { content }),
  deleteComment: (bugId: number, commentId: number) => http.delete(`/bugs/${bugId}/comments/${commentId}`),
  listAttachments: (id: number) => http.get(`/bugs/${id}/attachments`),
  presignUpload: (id: number, data: any) => http.post(`/bugs/${id}/attachments/presign`, data),
  confirmUpload: (id: number, data: any) => http.post(`/bugs/${id}/attachments/confirm`, data),
  deleteAttachment: (bugId: number, attachmentId: number) => http.delete(`/bugs/${bugId}/attachments/${attachmentId}`),
  downloadUrl: (bugId: number, attachmentId: number) => `/api/v1/bugs/${bugId}/attachments/${attachmentId}/download`,
}

export const imageApi = {
  presign: (filename: string, contentType: string) =>
    http.post('/images/presign', { filename, content_type: contentType }),
}

export const statsApi = {
  overview: (projectId?: number) => http.get('/stats/overview', { params: projectId ? { project_id: projectId } : {} }),
  trend: (projectId?: number, days = 14) => http.get('/stats/trend', { params: projectId ? { project_id: projectId, days } : { days } }),
  versionReport: (projectId: number, versionId: number) =>
    http.get('/stats/version-report', { params: { project_id: projectId, version_id: versionId } }),
  my: (projectId?: number) => http.get('/stats/my', { params: projectId ? { project_id: projectId } : {} }),
  mySummary: (projectId?: number) => http.get('/stats/my-summary', { params: projectId ? { project_id: projectId } : {} }),
  myBugs: (tab: string, page = 1, pageSize = 10, projectId?: number) =>
    http.get('/stats/my-bugs', { params: projectId ? { tab, page, page_size: pageSize, project_id: projectId } : { tab, page, page_size: pageSize } }),
  recentActivity: (limit = 20, projectId?: number) =>
    http.get('/stats/recent-activity', { params: projectId ? { limit, project_id: projectId } : { limit } }),
}

export const configApi = {
  // 流转规则
  listTransitionRules: () => http.get('/config/transition-rules'),
  updateTransitionRule: (fromStatus: string, toStatus: string, data: any) =>
    http.put(`/config/transition-rules/${fromStatus}/${toStatus}`, data),
}

export const rolesApi = {
  // 权限点目录
  listPermissions: () => http.get('/rbac/permissions'),
  // 角色 CRUD（含每个角色的权限点集合）
  listRoles: () => http.get('/rbac/roles'),
  createRole: (data: { name: string; label: string; color?: string; description?: string; permissions: string[] }) =>
    http.post('/rbac/roles', data),
  updateRole: (roleId: number, data: { label: string; color?: string; description?: string; permissions: string[] }) =>
    http.put(`/rbac/roles/${roleId}`, data),
  deleteRole: (roleId: number) => http.delete(`/rbac/roles/${roleId}`),
}

export const testCaseApi = {
  list: (projectId: number, params?: any) =>
    http.get(`/projects/${projectId}/testcases`, { params }),
  listAll: (params?: any) =>
    http.get('/testcases', { params }),
  getById: (caseId: number) =>
    http.get(`/testcases/${caseId}`),
  listRunsById: (caseId: number) =>
    http.get(`/testcases/${caseId}/runs`),
  get: (projectId: number, caseId: number) =>
    http.get(`/projects/${projectId}/testcases/${caseId}`),
  create: (projectId: number, data: any) =>
    http.post(`/projects/${projectId}/testcases`, data),
  update: (projectId: number, caseId: number, data: any) =>
    http.put(`/projects/${projectId}/testcases/${caseId}`, data),
  delete: (projectId: number, caseId: number) =>
    http.delete(`/projects/${projectId}/testcases/${caseId}`),
  listRuns: (projectId: number, caseId: number) =>
    http.get(`/projects/${projectId}/testcases/${caseId}/runs`),
  createRun: (projectId: number, caseId: number, data: any) =>
    http.post(`/projects/${projectId}/testcases/${caseId}/runs`, data),
  relatedCases: (bugId: number) =>
    http.get(`/bugs/${bugId}/related-cases`),
}

export const systemApi = {
  getEmailSettings: () => http.get('/system/email-settings'),
  updateEmailSettings: (data: any) => http.put('/system/email-settings', data),
  testEmail: (toEmail: string) => http.post('/system/email-test', { to_email: toEmail }),
  getFeishuSettings: () => http.get('/system/feishu-settings'),
  updateFeishuSettings: (data: any) => http.put('/system/feishu-settings', data),
}
