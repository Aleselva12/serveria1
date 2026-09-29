import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const proxy = {
    "/backend": {
      target: env.CORA_API_TARGET || "http://127.0.0.1:8000",
      changeOrigin: true,
      rewrite: (path: string) => path.replace(/^\/backend/, ""),
    },
  };
  return {
    plugins: [react()],
    server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy },
    preview: { host: "127.0.0.1", proxy },
  };
});
