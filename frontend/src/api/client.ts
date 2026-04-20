import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// ── Request interceptor: attach Bearer token ───────────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().accessToken
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── Response interceptor: handle 401 with token refresh ───────────────────
let isRefreshing = false
let failedQueue: Array<{ resolve: (value: string) => void; reject: (reason?: any) => void }> = []

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error)
    else prom.resolve(token!)
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          if (originalRequest.headers) originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = useAuthStore.getState().refreshToken
      if (!refreshToken) {
        useAuthStore.getState().logout()
        return Promise.reject(error)
      }

      try {
        const response = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        })
        const { access_token, refresh_token: newRefresh } = response.data
        useAuthStore.getState().setTokens(access_token, newRefresh)
        processQueue(null, access_token)
        if (originalRequest.headers) originalRequest.headers.Authorization = `Bearer ${access_token}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        useAuthStore.getState().logout()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Show error toast for non-auth errors
    if (error.response?.status !== 401) {
      const detail = (error.response?.data as any)?.detail
      const rawError = (error.response?.data as any)?.error
      const requestId = error.response?.headers?.['x-request-id'] || (error.response?.data as any)?.request_id
      if (detail && typeof detail === 'string' && !originalRequest.url?.includes('/auth/')) {
        const suffix = requestId ? ` (Request ID: ${requestId})` : ''
        const message = rawError && typeof rawError === 'string'
          ? `${detail} ${rawError}${suffix}`
          : `${detail}${suffix}`
        toast.error(message, { duration: 8000 })
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
