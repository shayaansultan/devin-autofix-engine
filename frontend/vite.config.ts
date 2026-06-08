import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build output goes straight into the backend's static dir so a single
// uvicorn process serves both the API and the dashboard.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../backend/app/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
