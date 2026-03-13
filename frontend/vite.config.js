import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const shouldOpenBrowser = process.env.VITE_OPEN_BROWSER !== 'false'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    open: shouldOpenBrowser,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
