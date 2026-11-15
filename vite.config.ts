import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// Configuración de Vite — aplicación independiente (sin dependencias de Figma).
const rootDir = import.meta.dirname

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(rootDir, './src'),
    },
  },
  server: {
    host: true,
    port: Number(process.env.PORT ?? 5173),
    strictPort: false,
    // El frontend nunca se conecta a la base de datos: consume la API de FastAPI.
    // El proxy evita problemas de CORS en desarrollo.
    proxy: {
      "/api": {
        target: process.env.API_URL ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true,
    port: Number(process.env.PORT ?? 4173),
  },
})
