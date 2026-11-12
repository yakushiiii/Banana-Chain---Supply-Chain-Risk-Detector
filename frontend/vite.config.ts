import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Listen on all interfaces so the dev server is reachable from outside its container
    host: true,
    port: 5173,
    // Same-origin requests to the API, so no CORS setup is needed in dev.
    // API_URL is read by Node (not the browser), e.g. http://api:5000 inside Compose.
    proxy: {
      '/health': process.env.API_URL ?? 'http://127.0.0.1:5000',
    },
  },
})
