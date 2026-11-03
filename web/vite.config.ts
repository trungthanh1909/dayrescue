import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const proxy = { '/api': { target: 'http://127.0.0.1:8001' } };
export default defineConfig({
  plugins: [react()], envDir: false,
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
  test: { environment: 'jsdom', setupFiles: ['./tests/setup.ts'], restoreMocks: true },
});
