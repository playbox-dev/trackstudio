import { defineConfig, preprocessCSS } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Use localhost for proxy target when SERVER_IP is 0.0.0.0 (since backend binds to all interfaces)
const PROXY_TARGET = process.env.PROXY_TARGET || 'localhost'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: `http://${PROXY_TARGET}:8002`,
        changeOrigin: true,
      },
      '/ws': {
        target: `ws://${PROXY_TARGET}:8002`,
        ws: true,
        changeOrigin: true,
      }
    }
  }
})
