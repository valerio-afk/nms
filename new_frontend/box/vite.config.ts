import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  base: "/box/",
  resolve: {
    alias: {
      '@nms/shared': path.resolve(__dirname, '../shared/src'),
    },
  },
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('@uppy')) {
            return 'uppy';
          }
        }
      }
    }
  }
})
