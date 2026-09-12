import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
export const videoViteConfig = (port = 7440, previewPort = 7442) =>
	defineConfig({
		base: "./",
		plugins: [react()],
		build: { outDir: "dist" },
		server: { host: "127.0.0.1", port, strictPort: true },
		preview: { host: "127.0.0.1", port: previewPort, strictPort: true },
	});
