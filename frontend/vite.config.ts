import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  build: {
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/leaflet')) {
            return 'vendor-leaflet';
          }
          if (id.includes('node_modules/recharts')) {
            return 'vendor-recharts';
          }
          if (id.includes('node_modules/html5-qrcode')) {
            return 'vendor-html5-qrcode';
          }
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'vendor-react';
          }
          if (id.includes('node_modules/@tanstack/react-query')) {
            return 'vendor-tanstack';
          }
          if (id.includes('node_modules/lucide-react')) {
            return 'vendor-icons';
          }
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})


