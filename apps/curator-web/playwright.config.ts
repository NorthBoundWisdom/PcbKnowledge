import { defineConfig, devices } from "@playwright/test";

const host = "127.0.0.1";
const port = 4173;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://${host}:${port}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { height: 900, width: 1440 } },
    },
  ],
  webServer: {
    command: "vite build && vite preview --host 127.0.0.1",
    env: {
      VITE_API_BASE_URL: "http://127.0.0.1:8000/api/v1",
      VITE_OIDC_CLIENT_ID: "pcbknowledge-curator-web",
      VITE_OIDC_ISSUER_URL: "http://127.0.0.1:8081/realms/pcbknowledge",
    },
    port,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
