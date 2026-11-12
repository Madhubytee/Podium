import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The FastAPI server runs on :8000; Vite forwards /api (including the live WebSocket) to it.
export default defineConfig({
  plugins: [react()],
  // Read the repo-root .env (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY).
  envDir: '..',
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', ws: true, changeOrigin: true },
    },
  },
})
