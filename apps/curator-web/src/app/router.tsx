import {
  Navigate,
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from "react-router-dom";

import { FoundationPage } from "../routes/FoundationPage";
import { NotFoundPage } from "../routes/NotFoundPage";
import { foundationRoutes } from "../routes/route-definitions";
import { AppShell } from "./AppShell";

export const applicationRouteObjects: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate replace to="/dashboard" /> },
      { path: "dashboard", element: <FoundationPage definition={foundationRoutes.dashboard} /> },
      { path: "intake", element: <FoundationPage definition={foundationRoutes.intake} /> },
      { path: "intake/new", element: <FoundationPage definition={foundationRoutes.intakeNew} /> },
      { path: "documents", element: <FoundationPage definition={foundationRoutes.documents} /> },
      {
        path: "documents/:revisionId",
        element: <FoundationPage definition={foundationRoutes.documentDetail} />,
      },
      { path: "review", element: <FoundationPage definition={foundationRoutes.review} /> },
      {
        path: "review/:taskId",
        element: <FoundationPage definition={foundationRoutes.reviewWorkbench} />,
      },
      { path: "entities", element: <FoundationPage definition={foundationRoutes.entities} /> },
      {
        path: "entities/resolve",
        element: <FoundationPage definition={foundationRoutes.entityResolver} />,
      },
      { path: "knowledge", element: <FoundationPage definition={foundationRoutes.knowledge} /> },
      {
        path: "knowledge/:recordId",
        element: <FoundationPage definition={foundationRoutes.knowledgeDetail} />,
      },
      { path: "search", element: <FoundationPage definition={foundationRoutes.search} /> },
      { path: "evals", element: <FoundationPage definition={foundationRoutes.evals} /> },
      { path: "audit", element: <FoundationPage definition={foundationRoutes.audit} /> },
      { path: "admin", element: <FoundationPage definition={foundationRoutes.admin} /> },
      { path: "admin/sources", element: <FoundationPage definition={foundationRoutes.sources} /> },
      { path: "admin/jobs", element: <FoundationPage definition={foundationRoutes.jobs} /> },
      { path: "jobs", element: <FoundationPage definition={foundationRoutes.jobs} /> },
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
