import axios from 'axios'

import { getAuthToken } from '@/auth'
import { getApiBaseUrl } from '@/config'

export const http = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
