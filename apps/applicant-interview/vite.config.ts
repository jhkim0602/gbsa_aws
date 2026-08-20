import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    // Same reason as the console: no CORS middleware on the backend, because production serves
    // the SPA and `/v1/*` from one origin. `ws` matters more here -- the interview itself runs
    // over the websocket.
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
