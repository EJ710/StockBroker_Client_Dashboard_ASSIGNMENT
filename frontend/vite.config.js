import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config. The dev server runs on :5173 (the origin we allow-listed in the
// backend CORS settings). We proxy /api and /ws to the FastAPI server on :8000
// so the frontend can use same-origin relative URLs in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
