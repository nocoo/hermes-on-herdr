import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "website" },
  server: { host: "127.0.0.1", port: 7430, strictPort: true },
});
