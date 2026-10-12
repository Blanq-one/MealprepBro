import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  oxc: { jsx: { runtime: "automatic" } }, // Vite 8 transforms with oxc
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    // a loaded machine (the fresh-clone check builds images beside it) can take over vitest's default 5 s
    testTimeout: 15_000,
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
