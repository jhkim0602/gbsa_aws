import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiProxyTarget =
    env.VITE_API_PROXY_TARGET?.trim() || "http://127.0.0.1:8080";

  return {
    plugins: [tailwindcss(), react()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      // The backend installs no CORS middleware, by design: in production each CloudFront
      // distribution routes `/v1/*` to the ALB beside its own SPA origin. Local development can
      // use either the host API or a deployed same-origin edge URL without exposing a second
      // origin to the browser.
      proxy: {
        "/v1": {
          target: apiProxyTarget,
          changeOrigin: true,
          // The interview room's transcript arrives over a websocket on this same prefix.
          ws: true,
        },
      },
    },
  };
});
