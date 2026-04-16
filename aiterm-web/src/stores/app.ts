import { defineStore } from "pinia"

import { getApiBaseUrl } from "@/config"

export const useAppStore = defineStore("app", {
  state: () => ({
    apiBaseUrl: getApiBaseUrl(),
  }),
})
