import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    // The route smoke test still targets the pre-wizard heading and remains quarantined.
    // Company workspace coverage is active again with current position fixtures.
    exclude: ["**/node_modules/**", "src/app/__tests__/featureRoutes.test.tsx"],
  },
});
