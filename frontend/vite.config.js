import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      // Force TDesign to use ESM build to avoid CJS react-19-adapter issue
      'tdesign-react$': 'tdesign-react/es',
      'tdesign-icons-react$': 'tdesign-icons-react/esm',
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
