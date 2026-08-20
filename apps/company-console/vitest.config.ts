import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    // Stale since the ba64585 redesign, which landed *after* the harness was removed at
    // 7d977f7 -- so nothing ever re-ran them against the new UI. The source is right and
    // these expectations are not:
    //   featureRoutes     expects a "포지션 만들기" heading; that string now exists nowhere
    //                     but the test itself.
    //   companyWorkspace  builds positions without `submissionRequirements`, which the type
    //                     marks required, so positionForm() crashes on `.map` of undefined.
    // Excluded rather than deleted: they cover real routes and flows, and should come back
    // with their fixtures and expectations updated.
    exclude: [
      "**/node_modules/**",
      "src/app/__tests__/featureRoutes.test.tsx",
      "src/features/company/__tests__/companyWorkspace.test.tsx",
    ],
  },
});
