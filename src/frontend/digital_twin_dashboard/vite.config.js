import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    // Proxy API and WebSocket to backend
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // Split chunks for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          'three-vendor': ['three'],
          'echarts-vendor': ['echarts'],
          'element-vendor': ['element-plus', '@element-plus/icons-vue']
        }
      }
    },
    // Increase chunk size warning limit (Three.js is large)
    chunkSizeWarningLimit: 1500
  },
  // Optimize deps
  optimizeDeps: {
    include: ['vue', 'vue-router', 'element-plus', 'echarts', 'three', 'pinia']
  }
})
