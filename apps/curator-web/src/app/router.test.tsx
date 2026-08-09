import { render, screen } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { validRuntimeConfig } from "../test/test-config";
import {
  createHumanUser,
  createServiceUser,
  createTrustedSession,
  FakeAuthClient,
} from "../test/fake-auth-client";
import { AppProviders } from "./AppProviders";
import { createTestRouter } from "./router";

const routeCases = [
  ["/dashboard", "Dashboard"],
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

afterEach(() => vi.restoreAllMocks());

describe.each(routeCases)("route %s", (path, heading) => {
  it(`renders the ${heading} foundation surface`, async () => {
    const router = createTestRouter([path]);
    const authClient = new FakeAuthClient(createHumanUser(["KNOWLEDGE_ADMIN"]));
    render(
      <AppProviders
        authClient={authClient}
        config={validRuntimeConfig}
        loadTrustedSession={() => Promise.resolve(createTrustedSession(["KNOWLEDGE_ADMIN"]))}
      >
        <RouterProvider router={router} />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeVisible();
    expect(screen.getByText("M0 foundation only · No business data")).toBeVisible();
  });
});

describe.each([
  ["/intake", "Intake inbox"],
  ["/documents", "Documents"],
  ["/documents/revision-123", "Document revision"],
] as const)("live M2 route %s", (path, heading) => {
  it(`renders the ${heading} surface without a foundation placeholder`, async () => {
    const router = createTestRouter([path]);
    const authClient = new FakeAuthClient(createHumanUser(["DATA_CURATOR"]));
    render(
      <AppProviders
        authClient={authClient}
        config={validRuntimeConfig}
        loadTrustedSession={() => Promise.resolve(createTrustedSession(["DATA_CURATOR"]))}
      >
        <RouterProvider router={router} />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeVisible();
    expect(screen.queryByText("M0 foundation only · No business data")).not.toBeInTheDocument();
  });
});

it("loads intake choices through the generated Bearer client", async () => {
  const projectId = "00000000-0000-7000-8000-000000000021";
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        access_scopes: [
          {
            id: "00000000-0000-7000-8000-000000000022",
            name: "Project evidence",
            project_id: projectId,
          },
        ],
        license_policies: [
          {
            access_scope_id: "00000000-0000-7000-8000-000000000022",
            allow_human_raw_access: true,
            allow_parse: true,
            id: "00000000-0000-7000-8000-000000000023",
            license_class: "PUBLIC_REFERENCE",
            name: "Public reference",
          },
        ],
        projects: [{ display_name: "Component Research", id: projectId }],
        source_organizations: [
          {
            authority_tier: "MANUFACTURER_PRIMARY",
            id: "00000000-0000-7000-8000-000000000024",
            name: "Example Semiconductor",
          },
        ],
      }),
      { headers: { "Content-Type": "application/json" }, status: 200 },
    ),
  );
  const router = createTestRouter(["/intake/new"]);
  const authClient = new FakeAuthClient(createHumanUser(["DATA_CURATOR"]));
  render(
    <AppProviders
      authClient={authClient}
      config={{ ...validRuntimeConfig, apiBaseUrl: "https://knowledge.example.test/api/v1" }}
      loadTrustedSession={() =>
        Promise.resolve(
          createTrustedSession([], [{ id: projectId, roles: ["DATA_CURATOR"] }]),
        )
      }
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByLabelText("PDF file")).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Intake project" })).toHaveTextContent(
    "Component Research",
  );
  const request = fetchSpy.mock.calls[0]?.[0];
  expect(request).toBeInstanceOf(Request);
  expect((request as Request).headers.get("Authorization")).toBe(
    "Bearer synthetic-access-token-held-only-by-the-test-object",
  );
  expect((request as Request).url).toContain("/intake/options");
});

it("redirects the workspace root to dashboard", async () => {
  const router = createTestRouter(["/"]);
  const authClient = new FakeAuthClient(createHumanUser(["KNOWLEDGE_ADMIN"]));
  render(
    <AppProviders
      authClient={authClient}
      config={validRuntimeConfig}
      loadTrustedSession={() => Promise.resolve(createTrustedSession(["KNOWLEDGE_ADMIN"]))}
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
  expect(router.state.location.pathname).toBe("/dashboard");
});

it("does not invent a fallback route or data surface", async () => {
  const router = createTestRouter(["/not-a-real-work-area"]);
  const authClient = new FakeAuthClient(createHumanUser(["KNOWLEDGE_ADMIN"]));
  render(
    <AppProviders
      authClient={authClient}
      config={validRuntimeConfig}
      loadTrustedSession={() => Promise.resolve(createTrustedSession(["KNOWLEDGE_ADMIN"]))}
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(
    await screen.findByRole("heading", { level: 1, name: "This workspace route does not exist" }),
  ).toBeVisible();
  expect(screen.getByText(/No fallback data was loaded/)).toBeVisible();
});

it("fails closed at a protected route when unauthenticated", async () => {
  const router = createTestRouter(["/documents"]);
  render(
    <AppProviders
      authClient={new FakeAuthClient()}
      config={validRuntimeConfig}
      loadTrustedSession={() => Promise.resolve(createTrustedSession(["KNOWLEDGE_ADMIN"]))}
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByRole("heading", { name: "Sign in to PcbKnowledge" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Documents" })).not.toBeInTheDocument();
});

it("fails closed when a human lacks the route capability", async () => {
  const router = createTestRouter(["/admin"]);
  const authClient = new FakeAuthClient(createHumanUser(["KNOWLEDGE_ADMIN"]));
  render(
    <AppProviders
      authClient={authClient}
      config={validRuntimeConfig}
      loadTrustedSession={() => Promise.resolve(createTrustedSession(["DATA_CURATOR"]))}
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByRole("heading", { name: "Access denied" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Administration" })).not.toBeInTheDocument();
});

it("does not grant organization administration from a project-only admin role", async () => {
  const router = createTestRouter(["/admin"]);
  const authClient = new FakeAuthClient(createHumanUser(["KNOWLEDGE_ADMIN"]));
  render(
    <AppProviders
      authClient={authClient}
      config={validRuntimeConfig}
      loadTrustedSession={() =>
        Promise.resolve(
          createTrustedSession([], [
            {
              id: "00000000-0000-7000-8000-000000000013",
              roles: ["KNOWLEDGE_ADMIN"],
            },
          ]),
        )
      }
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByRole("heading", { name: "Access denied" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Administration" })).not.toBeInTheDocument();
});

it("rejects AGENT_SERVICE from the browser client", async () => {
  const router = createTestRouter(["/dashboard"]);
  const authClient = new FakeAuthClient(createServiceUser());
  render(
    <AppProviders
      authClient={authClient}
      config={validRuntimeConfig}
      loadTrustedSession={() => Promise.resolve(createTrustedSession(["DATA_CURATOR"]))}
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByRole("heading", { name: "Identity not permitted" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Dashboard" })).not.toBeInTheDocument();
});

it("completes an authorization callback and restores the safe route", async () => {
  const router = createTestRouter(["/auth/callback?code=synthetic&state=synthetic"]);
  const authClient = new FakeAuthClient();
  authClient.callbackUser = createHumanUser(["DATA_CURATOR"], { returnUrl: "/documents" });
  render(
    <AppProviders
      authClient={authClient}
      config={validRuntimeConfig}
      loadTrustedSession={() => Promise.resolve(createTrustedSession(["DATA_CURATOR"]))}
    >
      <RouterProvider router={router} />
    </AppProviders>,
  );

  expect(await screen.findByRole("heading", { name: "Documents" })).toBeVisible();
  expect(router.state.location.pathname).toBe("/documents");
});
