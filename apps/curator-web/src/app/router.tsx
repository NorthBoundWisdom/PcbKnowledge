import {
  Navigate,
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from "react-router-dom";

import { AuthenticationBoundary } from "../auth/AuthenticationBoundary";
import { RequireCapability } from "../auth/RequireCapability";
import type { BrowserCapability } from "../auth/auth-types";
import { FoundationPage } from "../routes/FoundationPage";
import { NotFoundPage } from "../routes/NotFoundPage";
import { AuthCallbackPage } from "../routes/auth/AuthCallbackPage";
import { AuthErrorPage } from "../routes/auth/AuthErrorPage";
import { LogoutCallbackPage } from "../routes/auth/LogoutCallbackPage";
import { SessionExpiredPage } from "../routes/auth/SessionExpiredPage";
import { foundationRoutes } from "../routes/route-definitions";
import { AppShell } from "./AppShell";

function protectedFoundationPage(
  definition: (typeof foundationRoutes)[keyof typeof foundationRoutes],
  capability: BrowserCapability,
) {
  return (
    <RequireCapability capability={capability}>
      <FoundationPage definition={definition} />
    </RequireCapability>
  );
}

export const applicationRouteObjects: RouteObject[] = [
  { path: "/auth/callback", element: <AuthCallbackPage /> },
  { path: "/auth/logout/callback", element: <LogoutCallbackPage /> },
  { path: "/auth/error", element: <AuthErrorPage /> },
  { path: "/auth/session-expired", element: <SessionExpiredPage /> },
  {
    path: "/",
    element: (
      <AuthenticationBoundary>
        <AppShell />
      </AuthenticationBoundary>
    ),
    children: [
      { index: true, element: <Navigate replace to="/dashboard" /> },
      {
        path: "dashboard",
        element: protectedFoundationPage(foundationRoutes.dashboard, "workspace:access"),
      },
      {
        path: "intake",
        element: protectedFoundationPage(foundationRoutes.intake, "intake:prepare"),
      },
      {
        path: "intake/new",
        element: protectedFoundationPage(foundationRoutes.intakeNew, "intake:prepare"),
      },
      {
        path: "documents",
        element: protectedFoundationPage(foundationRoutes.documents, "evidence:read"),
      },
      {
        path: "documents/:revisionId",
        element: protectedFoundationPage(foundationRoutes.documentDetail, "evidence:read"),
      },
      {
        path: "review",
        element: protectedFoundationPage(foundationRoutes.review, "review:participate"),
      },
      {
        path: "review/:taskId",
        element: protectedFoundationPage(foundationRoutes.reviewWorkbench, "review:participate"),
      },
      {
        path: "entities",
        element: protectedFoundationPage(foundationRoutes.entities, "evidence:read"),
      },
      {
        path: "entities/resolve",
        element: protectedFoundationPage(foundationRoutes.entityResolver, "review:participate"),
      },
      {
        path: "knowledge",
        element: protectedFoundationPage(foundationRoutes.knowledge, "evidence:read"),
      },
      {
        path: "knowledge/:recordId",
        element: protectedFoundationPage(foundationRoutes.knowledgeDetail, "evidence:read"),
      },
      {
        path: "search",
        element: protectedFoundationPage(foundationRoutes.search, "evidence:read"),
      },
      {
        path: "evals",
        element: protectedFoundationPage(foundationRoutes.evals, "evaluation:read"),
      },
      {
        path: "audit",
        element: protectedFoundationPage(foundationRoutes.audit, "audit:read"),
      },
      {
        path: "admin",
        element: protectedFoundationPage(foundationRoutes.admin, "admin:operate"),
      },
      {
        path: "admin/sources",
        element: protectedFoundationPage(foundationRoutes.sources, "admin:operate"),
      },
      {
        path: "admin/jobs",
        element: protectedFoundationPage(foundationRoutes.jobs, "admin:operate"),
      },
      {
        path: "jobs",
        element: protectedFoundationPage(foundationRoutes.jobs, "admin:operate"),
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(applicationRouteObjects);
}

export function createTestRouter(initialEntries: string[]) {
  return createMemoryRouter(applicationRouteObjects, { initialEntries });
}
