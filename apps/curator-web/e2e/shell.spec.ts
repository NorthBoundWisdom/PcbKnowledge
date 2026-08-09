import { expect, test } from "@playwright/test";

import { resolveLiveE2eBaseUrl } from "../src/config/live-e2e-origin";

const liveBaseUrl = resolveLiveE2eBaseUrl(process.env);

if (liveBaseUrl === undefined) {
  test("serves a static health artifact", async ({ request }) => {
    const response = await request.get("/healthz");

    expect(response.ok()).toBe(true);
    expect((await response.text()).trim()).toBe("ok");
  });
} else {
  test("serves API liveness through the live gateway", async ({ request }) => {
    const response = await request.get("/healthz");

    expect(response.ok()).toBe(true);
    expect(await response.json()).toEqual({
      service: "pcbknowledge-api",
      status: "alive",
      version: "0.1.0",
    });
  });
}

test("fails closed before loading a protected workspace route", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page.getByRole("heading", { level: 1, name: "Sign in to PcbKnowledge" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toHaveCount(0);
  await expect(page.getByText(/Service accounts.*are denied/)).toBeVisible();
});

test("shows a bounded authentication error without reflecting provider payload", async ({ page }) => {
  await page.goto("/auth/error?reason=unknown&error_description=do-not-reflect-this-value");

  await expect(
    page.getByRole("heading", { level: 1, name: "Authentication could not be completed" }),
  ).toBeVisible();
  await expect(page.getByText("do-not-reflect-this-value")).toHaveCount(0);
});
