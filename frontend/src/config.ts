declare global {
  interface Window {
    __CONFIG__?: {
      API_BASE_URL?: string
    }
  }
}

export function getApiBaseUrl(): string {
  const runtimeConfig = window.__CONFIG__?.API_BASE_URL
  const envConfig = import.meta.env.VITE_API_BASE_URL
  return runtimeConfig ?? envConfig ?? ''
}
