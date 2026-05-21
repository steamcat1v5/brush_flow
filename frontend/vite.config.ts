import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载当前环境的 .env 文件
  const env = loadEnv(mode, process.cwd(), '');

  const frontendPort = parseInt(env.VITE_PORT || '3000');
  const backendUrl = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';
  const backendWsUrl = backendUrl.replace('http', 'ws');

  return {
    plugins: [react()],
    server: {
      port: frontendPort,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
        '/ws': {
          target: backendWsUrl,
          ws: true,
        },
      },
    },
  };
})
