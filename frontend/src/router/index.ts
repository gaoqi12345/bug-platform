import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      component: () => import('@/views/Layout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/dashboard',
        },
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue'),
        },
        {
          path: 'bugs',
          name: 'BugList',
          component: () => import('@/views/BugList.vue'),
        },
        {
          path: 'bugs/create',
          name: 'BugCreate',
          component: () => import('@/views/BugCreate.vue'),
        },
        {
          path: 'bugs/:id',
          name: 'BugDetail',
          component: () => import('@/views/BugDetail.vue'),
        },
        {
          path: 'stats',
          name: 'Stats',
          component: () => import('@/views/Stats.vue'),
        },
        {
          path: 'settings',
          name: 'ProjectSettings',
          component: () => import('@/views/ProjectSettings.vue'),
        },
        {
          path: 'testcases',
          name: 'TestCase',
          component: () => import('@/views/TestCase.vue'),
        },
        {
          path: 'testcases/:id',
          name: 'TestCaseDetail',
          component: () => import('@/views/TestCaseDetail.vue'),
        },
        {
          path: 'admin',
          name: 'Admin',
          component: () => import('@/views/Admin.vue'),
          meta: { requiresSuperAdmin: true },
        },
        {
          path: 'profile',
          name: 'Profile',
          component: () => import('@/views/Profile.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 路由守卫
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth !== false && !auth.isLoggedIn) {
    return '/login'
  }
  if (to.path === '/login' && auth.isLoggedIn) {
    return '/'
  }
  // 超管页面守卫
  if (to.meta.requiresSuperAdmin && !auth.user?.is_super_admin) {
    return '/dashboard'
  }
})

export default router
