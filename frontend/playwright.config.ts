import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "iphone", use: { ...devices["iPhone 13"], browserName: "chromium" } },
    { name: "android", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "uv run --python 3.12 --with-requirements requirements.txt python -m tests.e2e_server",
      cwd: "../backend",
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run build && npm run preview -- --host 127.0.0.1",
      cwd: ".",
      env: { VITE_API_URL: "http://127.0.0.1:8001" },
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
