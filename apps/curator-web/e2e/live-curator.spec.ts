import { Buffer } from "node:buffer";
import { randomUUID } from "node:crypto";
import { lstatSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { env } from "node:process";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import {
  isLoopbackHttpUrl,
  liveE2eBaseUrlVariable,
} from "../src/config/live-e2e-origin";

const passwordFileVariable = "PCBKNOWLEDGE_E2E_PASSWORD_FILE";
const localUsername = "pcbknowledge-curator";

function liveApplicationOrigin(): string {
  const configured = env[liveE2eBaseUrlVariable];
  if (configured === undefined) {
    throw new Error("Live Curator E2E requires its explicit application origin");
  }
  return new URL(configured).origin;
}

function passwordFilePath(): string {
  const configured = env[passwordFileVariable];
  if (configured !== undefined) {
    if (configured.trim().length === 0) {
      throw new Error(`${passwordFileVariable} must name an owner-only file`);
    }
    return resolve(configured);
  }
  return fileURLToPath(
    new URL("../../../deploy/secrets/local_curator_password", import.meta.url),
  );
}

function readOwnerOnlyLocalPassword(): string {
  const path = passwordFilePath();
  let metadata: ReturnType<typeof lstatSync>;
  let value: string;
  try {
    metadata = lstatSync(path);
    value = readFileSync(path, "utf8").trim();
  } catch {
    throw new Error("The live Curator password file is missing or unreadable");
  }
  if (
    !metadata.isFile() ||
    (metadata.mode & 0o077) !== 0 ||
    (metadata.mode & 0o400) === 0
  ) {
    throw new Error("The live Curator password file must be an owner-readable, owner-only regular file");
  }
  if (!/^[0-9a-f]{64}$/u.test(value)) {
    throw new Error("The live Curator password file does not contain the managed credential format");
  }
  return value;
}

async function selectFirstAuthorizedOption(page: Page, label: string) {
  const select = page.getByRole("combobox", { name: label });
  await expect(select).toBeEnabled();
  await select.click();
  const option = page.locator('[role="option"]:not([aria-disabled="true"])').first();
  await expect(option).toBeVisible();
  await option.click();
}

test("live PKCE intake reaches the vault and creates an audited original-file navigation", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const password = readOwnerOnlyLocalPassword();
  const applicationOrigin = liveApplicationOrigin();
  const unique = `${Date.now()}-${randomUUID().slice(0, 8)}`;
  const title = `Live intake ${unique}`;
  const pdf = Buffer.from(
    [
      "%PDF-1.7",
      "% PcbKnowledge synthetic live browser qualification",
      "1 0 obj",
      "<< /Type /Catalog >>",
      "endobj",
      "trailer",
      "<< /Root 1 0 R >>",
      "%%EOF",
      "",
    ].join("\n"),
    "ascii",
  );

  await page.goto("/intake/new");
  await expect(page.getByRole("heading", { level: 1, name: "Sign in to PcbKnowledge" })).toBeVisible();
  await page.getByRole("button", { name: "Sign in with organization identity" }).click();

  await expect(page.locator("#username")).toBeVisible();
  if (!isLoopbackHttpUrl(page.url())) {
    throw new Error("Refusing to submit the local Curator credential outside loopback HTTP");
  }
  await page.locator("#username").fill(localUsername);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();

  await expect(page.getByRole("heading", { level: 1, name: "New document intake" })).toBeVisible({
    timeout: 30_000,
  });
  await selectFirstAuthorizedOption(page, "Intake project");
  await page.getByLabel("PDF file").setInputFiles({
    buffer: pdf,
    mimeType: "application/pdf",
    name: `live-${unique}.pdf`,
  });
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Document number (optional)").fill(`LIVE-${unique}`);
  await page.getByLabel("Revision").fill("A");
  await selectFirstAuthorizedOption(page, "Source organization");
  await selectFirstAuthorizedOption(page, "Access scope");
  await selectFirstAuthorizedOption(page, "License policy");
  await page
    .getByRole("checkbox", {
      name: "I confirmed the source, project scope, license policy, and document identity.",
    })
    .check();
  await page.getByRole("button", { name: "Upload and verify PDF" }).click();

  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText(/^[0-9a-f]{64}$/u)).toBeVisible();

  await page.getByRole("link", { exact: true, name: "Documents" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Documents" })).toBeVisible();
  await expect(page.getByRole("link", { exact: true, name: title })).toBeVisible();
  await page.getByRole("link", { exact: true, name: title }).click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();

  let externalOriginalNavigationObserved = false;
  await page.route("**/*", async (route) => {
    const request = route.request();
    const target = new URL(request.url());
    if (
      request.isNavigationRequest() &&
      request.frame() === page.mainFrame() &&
      request.method() === "GET" &&
      target.origin !== applicationOrigin
    ) {
      externalOriginalNavigationObserved = request.headers().authorization === undefined;
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
  const auditedAuthorization = page.waitForResponse((response) => {
    const request = response.request();
    return (
      request.method() === "POST" &&
      new URL(request.url()).pathname.endsWith("/original-download")
    );
  });
  await page.getByRole("button", { name: "Open authorized original" }).click();
  expect((await auditedAuthorization).ok()).toBe(true);
  await expect.poll(() => externalOriginalNavigationObserved).toBe(true);
});
