import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  base: '/',
  build: {
    outDir: '../backend/dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('element-plus')) {
            return 'element-plus'
          }

          if (id.includes('vue-router')) {
            return 'vue-router'
          }

          if (id.includes('pinia')) {
            return 'pinia'
          }

          if (id.includes('axios')) {
            return 'axios'
          }

          if (id.includes('node_modules')) {
            return 'vendor'
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      vue: 'vue/dist/vue.esm-bundler.js',
    },
  },
  server: {
    port: 18085,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:18084',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:18084',
        changeOrigin: true,
      },
    },
  },
})
