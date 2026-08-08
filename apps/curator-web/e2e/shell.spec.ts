import { expect, test } from "@playwright/test";

test("serves a static health artifact", async ({ request }) => {
  const response = await request.get("/healthz");

  expect(response.ok()).toBe(true);
  expect((await response.text()).trim()).toBe("ok");
});

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
