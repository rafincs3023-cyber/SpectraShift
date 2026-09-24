import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api to the FastAPI backend so the app works from any host
    // (e.g. another device on the LAN) when VITE_API_BASE_URL is empty.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
