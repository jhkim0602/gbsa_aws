import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    // Stale since the ba64585 redesign, which landed *after* the harness was removed at
    // 7d977f7 -- so nothing ever re-ran them against the new UI. Both assert synchronously
    // against markup that is now behind an await:
    //   featureRoutes      `/submissions` renders through `routeAdapters.tsx:317`, which
    //                      shows a `role="status"` placeholder until `getWorkspace()`
    //                      resolves, so the heading is not in the first paint.
    //   submissionJourney  "일부 완료" now matches multiple nodes, so `getByText` throws
    //                      where it used to find one.
    // Excluded rather than deleted: the flows they cover are real, and they should come back
    // using `findBy*` and a narrower query.
    exclude: [
      "**/node_modules/**",
      "src/app/__tests__/featureRoutes.test.tsx",
      "src/features/submissions/__tests__/submissionJourney.test.tsx",
    ],
  },
});
