import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: './' keeps asset paths relative so the built bundle works when served
// from a GitHub Pages project subpath (e.g. /archeologic/).
export default defineConfig({
  base: "./",
  plugins: [react()],
});
