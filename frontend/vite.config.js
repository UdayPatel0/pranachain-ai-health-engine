// VitaLens React app · Owner: Nancy · built with AI assistance (Claude), reviewed by the team
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const web = fileURLToPath(new URL("../web", import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: "./",
  // Same JSON as the HTML demo: web/data/index.json and web/data/chunks/*.json are served at /index.json and /chunks/
  publicDir: fileURLToPath(new URL("../web/data", import.meta.url)),
  // explain.js is shared with the HTML demo (one copy of the safety + readability rules)
  resolve: { alias: { "@shared": web } },
  server: { port: 5173, fs: { allow: [".."] } },
});
