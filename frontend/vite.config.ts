import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),
    react()
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allow access through tunnels / LAN hosts (Render previews, ngrok,
    // sandbox proxies) instead of the default localhost-only guard.
    allowedHosts: true,
    proxy: {
      // Lets the browser call same-origin `/api/v1/...` during development
      // when the FastAPI service runs on its default port.
      '/api/v1': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
