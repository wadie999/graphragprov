import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");

  const proxyTarget =
    env.GRAPHRAGPROV_API_PROXY ??
    "http://127.0.0.1:8080";

  return {
    plugins: [react()],

    server: {
      host: "127.0.0.1",
      port: 5173,

      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});