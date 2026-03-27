import { readFileSync } from "node:fs";
import { defineConfig } from "vitest/config";

const { version } = JSON.parse(readFileSync("./package.json", "utf-8"));

export default defineConfig({
  define: {
    __VERSION__: JSON.stringify(version),
  },
  test: {
    globals: true,
    include: ["tests/**/*.test.ts"],
  },
});
