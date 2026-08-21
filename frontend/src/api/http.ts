import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  // 数组参数用「重复键」序列化（FastAPI 兼容）：
  //   status_list: ['a', 'b'] → status_list=a&status_list=b
  // 否则 axios 默认序列化为 status_list[]=a&status_list[]=b（带 [] 后缀），
  // FastAPI 无法识别 status_list[] 键，导致数组筛选参数丢失（如 Bug 状态筛选无效）。
  paramsSerializer: {
    serialize: (params: Record<string, any>) => {
      const search = new URLSearchParams()
      for (const [key, val] of Object.entries(params || {})) {
        if (val === null || val === undefined || val === '') continue
        if (Array.isArray(val)) {
          val.forEach(v => search.append(key, String(v)))
        } else {
          search.append(key, String(val))
        }
      }
      return search.toString()
    },
  },
})

// 请求拦截：自动注入 Token
http.interceptors.request.use(config => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截：统一错误处理
http.interceptors.response.use(
  res => res.data,
  err => {
    if (err.response?.status === 401) {
      useAuthStore().logout()
      window.location.href = '/login'
    }
    const msg = err.response?.data?.detail || '请求失败'
    return Promise.reject(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
)

export default http
