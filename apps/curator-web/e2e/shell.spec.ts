import { expect, test } from "@playwright/test";

test("serves a static health artifact", async ({ request }) => {
  const response = await request.get("/healthz");

  expect(response.ok()).toBe(true);
  expect((await response.text()).trim()).toBe("ok");
});

test("restores routes in the desktop foundation shell", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("M0 foundation only · No business data")).toBeVisible();

  await page.getByRole("link", { name: "Documents" }).click();
  await expect(page).toHaveURL(/\/documents$/);
  await expect(page.getByRole("heading", { level: 1, name: "Documents" })).toBeVisible();
});
