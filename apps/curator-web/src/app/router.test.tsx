import { render, screen } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { validRuntimeConfig } from "../test/test-config";
import { AppProviders } from "./AppProviders";
import { createTestRouter } from "./router";

const routeCases = [
  ["/dashboard", "Dashboard"],
  ["/intake", "Intake inbox"],
  ["/intake/new", "New document intake"],
  ["/documents", "Documents"],
  ["/documents/revision-123", "Document revision"],
  ["/review", "Review queue"],
  ["/review/task-123", "Review workbench"],
  ["/entities", "Entities"],
  ["/entities/resolve", "Entity resolver"],
  ["/knowledge", "Knowledge explorer"],
  ["/knowledge/record-123", "Knowledge record"],
  ["/search", "Evidence search"],
  ["/evals", "Evaluation center"],
  ["/audit", "Audit explorer"],
  ["/admin", "Administration"],
  ["/admin/sources", "Sources and licenses"],
  ["/admin/jobs", "Job monitor"],
  ["/jobs", "Job monitor"],
] as const;

describe.each(routeCases)("route %s", (path, heading) => {
  it(`renders the ${heading} foundation surface`, async () => {
    const router = createTestRouter([path]);
    render(
      <AppProviders config={validRuntimeConfig}>
        <RouterProvider router={router} />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeVisible();
    expect(screen.getByText("M0 foundation only · No business data")).toBeVisible();
  });
});

it("redirects the workspace root to dashboard", async () => {
  const router = createTestRouter(["/"]);
  render(
    <AppProviders config={validRuntimeConfig}>
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
  expect(router.state.location.pathname).toBe("/dashboard");
});

it("does not invent a fallback route or data surface", async () => {
  const router = createTestRouter(["/not-a-real-work-area"]);
  render(
    <AppProviders config={validRuntimeConfig}>
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(
    await screen.findByRole("heading", { level: 1, name: "This workspace route does not exist" }),
  ).toBeVisible();
  expect(screen.getByText(/No fallback data was loaded/)).toBeVisible();
});
