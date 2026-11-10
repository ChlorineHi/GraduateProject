import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

function loopbackPort(value: string | undefined, fallback: number): number {
  if (value && /^[0-9]+$/.test(value)) {
    const port = Number(value)
    if (port >= 1 && port <= 65535) return port
  }
  return fallback
}

const apiPort = loopbackPort(process.env.UNLAB_API_PORT, 8000)
const webPort = loopbackPort(process.env.UNLAB_WEB_PORT, 5173)

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: webPort,
    proxy: { '/api': `http://127.0.0.1:${apiPort}` },
  },
})
