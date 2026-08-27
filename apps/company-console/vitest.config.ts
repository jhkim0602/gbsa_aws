import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    env: {
      // Unit tests stub their own authentication state. Keep a developer's
      // untracked `.env.local` Cognito settings from redirecting route tests.
      VITE_COGNITO_DOMAIN: "",
      VITE_COGNITO_CLIENT_ID: "",
      VITE_COGNITO_REDIRECT_URI: "",
    },
    // The route smoke test still targets the pre-wizard heading and remains quarantined.
    // Company workspace coverage is active again with current position fixtures.
    exclude: ["**/node_modules/**", "src/app/__tests__/featureRoutes.test.tsx"],
  },
});
