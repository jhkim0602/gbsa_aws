import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // The backend installs no CORS middleware, by design: in production each CloudFront
    // distribution routes `/v1/*` to the ALB beside its own SPA origin, so the browser only ever
    // makes same-origin requests. Proxying here reproduces that, and is why the console needs no
    // VITE_API_BASE_URL locally -- a direct `http://localhost:8080` would be cross-origin and
    // every request would fail preflight.
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
        // The interview room's transcript arrives over a websocket on this same prefix.
        ws: true,
      },
    },
  },
});
