import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "/index.html",
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:9109",
      "/ws": {
        target: "ws://127.0.0.1:9109",
        ws: true,
      },
    },
  },
});
