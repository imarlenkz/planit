import { defineConfig, devices } from "@playwright/test";

/**
 * E2E: runs against a running stack (docker compose → http://localhost, or `npm run dev` + backend → :3000).
 * BASE_URL=http://localhost:3000 npm run test:e2e
 * CHROMIUM_PATH can point to a preinstalled Chromium binary.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 240_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    acceptDownloads: true,
    locale: "kk-KZ",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
