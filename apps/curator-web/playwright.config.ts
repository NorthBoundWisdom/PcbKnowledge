import { defineConfig, devices } from "@playwright/test";

import { resolveLiveE2eBaseUrl } from "./src/config/live-e2e-origin";

const host = "127.0.0.1";
const port = 4173;
const liveBaseUrl = resolveLiveE2eBaseUrl(process.env);
const liveMode = liveBaseUrl !== undefined;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: !liveMode,
  forbidOnly: Boolean(process.env.CI),
  retries: liveMode ? 0 : process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  testIgnore: liveMode ? [] : ["**/live-*.spec.ts"],
  use: {
    baseURL: liveBaseUrl ?? `http://${host}:${port}`,
    screenshot: "off",
    trace: liveMode ? "off" : "on-first-retry",
    video: "off",
  },
  workers: liveMode ? 1 : undefined,
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { height: 900, width: 1440 } },
    },
  ],
  webServer: liveMode
    ? undefined
    : {
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
