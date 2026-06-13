import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Vite dev-server config.
//
// Ports are configurable via env vars so the app never hard-fails on another
// machine where a port might already be in use:
//
//   VITE_PORT        preferred dev-server port (default 5173). If it's taken,
//                    Vite automatically falls back to the next free port — the
//                    app still works because the frontend calls the API through
//                    relative URLs (/api, /ws), not a hard-coded port.
//   VITE_API_TARGET  where the backend lives (default http://localhost:8000).
//                    Set this if you run the backend on a different host/port.
//
// Copy frontend/.env.example to frontend/.env to override either value.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const apiTarget = env.VITE_API_TARGET || "http://localhost:8000";
  // Derive the WebSocket target from the API target (http->ws, https->wss).
  const wsTarget = apiTarget.replace(/^http/, "ws");
  const port = Number(env.VITE_PORT) || 5173;

  return {
    plugins: [react()],
    server: {
      port,
      // strictPort is left at its default (false) on purpose: if `port` is
      // already in use, Vite picks the next free port instead of crashing.
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
        "/ws": { target: wsTarget, ws: true },
      },
    },
  };
});
