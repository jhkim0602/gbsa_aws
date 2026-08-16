import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: "line",
  timeout: 30_000,
  use: {
    baseURL: process.env.COMPANY_E2E_BASE_URL ?? "http://127.0.0.1:5173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "company-chrome",
      testMatch: "company-console.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
      },
    },
    {
      name: "applicant-chrome",
      testMatch: "applicant-journey.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: process.env.APPLICANT_E2E_BASE_URL ?? "http://127.0.0.1:5174",
        channel: "chrome",
      },
    },
  ],
});
