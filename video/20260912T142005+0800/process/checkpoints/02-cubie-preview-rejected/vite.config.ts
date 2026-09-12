import { videoViteConfig } from "@hexly/video-kit/vite";
import { mergeConfig } from "vite";

export default mergeConfig(videoViteConfig(7460, 7462), {
  build: { outDir: "website" },
});
