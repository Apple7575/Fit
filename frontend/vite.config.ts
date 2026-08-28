import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // 로컬 백엔드(Spring Boot :8080)로 전달. 배포 시엔 Nginx 가 같은 역할을 한다.
      '/api': 'http://localhost:8080',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // 테스트는 항상 실제 API 경로(fetch 스텁)를 검증한다. mock 분기를 타지 않도록 고정.
    env: { VITE_API_MOCK: 'false' },
  },
})
