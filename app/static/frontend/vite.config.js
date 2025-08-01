// static/frontend/vite.config.js
import { defineConfig } from 'vite'

export default defineConfig({
  root: '.', // Where index.html lives
  base: '/assets/', // Ensures index.html references JS/CSS under /assets/

  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsDir: '.', // Flatten assets into /dist directly (not dist/assets)
    rollupOptions: {
      input: './index.html',
    },
  },

  server: {
    proxy: {
      '/api': {
        target: 'http://flask-app:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})