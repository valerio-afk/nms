import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const vmTarget = env.VITE_BACKEND_TARGET || 'http://192.168.0.45';

  return {
    base: "/",
    plugins: [
      react({
        babel: {
          plugins: [['babel-plugin-react-compiler']],
        },
      }),
    ],
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: vmTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
