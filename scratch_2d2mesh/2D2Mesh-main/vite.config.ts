import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("three") || id.includes("@react-three") || id.includes("troika") || id.includes("maath")) {
            return "vendor-three";
          }
          if (id.includes("recharts") || id.includes("d3-") || id.includes("victory")) {
            return "vendor-charts";
          }
          if (id.includes("react") || id.includes("scheduler") || id.includes("zustand")) {
            return "vendor-react";
          }
          return "vendor";
        },
      },
    },
  },
});