/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        // Библиотеки — отдельными файлами: они меняются редко и остаются в кэше браузера между версиями.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('/katex/')) return 'katex'
          if (id.includes('/react-router')) return 'router'
          if (/\/(react|react-dom|scheduler)\//.test(id)) return 'react'
          return undefined
        },
      },
    },
  },
  server: {
    proxy: { '/api': 'http://localhost:8000', '/figures': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
  },
})
