import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    pool: 'threads',
    fileParallelism: false,
    maxWorkers: 1,
    isolate: false,
    testTimeout: 20000,
    hookTimeout: 20000,
    teardownTimeout: 5000,
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
})
