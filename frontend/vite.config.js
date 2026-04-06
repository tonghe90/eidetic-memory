import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/connectors": "http://127.0.0.1:8765",
      "/ingest": "http://127.0.0.1:8765",
      "/settings": "http://127.0.0.1:8765",
      "/search": "http://127.0.0.1:8765",
      "/health": "http://127.0.0.1:8765",
    },
  },
});
