import { useCallback, useEffect, useMemo } from "react";

import type { BrowserProjectGrant, BrowserSession } from "../../auth/auth-types";
import { useAuthentication } from "../../auth/use-authentication";
import { useWorkspaceStore } from "../../state/workspace-store";

export class ProjectSelectionError extends Error {
  constructor() {
    super("The selected project is not present in the trusted browser session");
    this.name = "ProjectSelectionError";
  }
}

export function projectSelectionWorkspaceKey(
  session: Pick<BrowserSession, "organizationId" | "subjectId">,
): string {
  return `${session.subjectId}:${session.organizationId}`;
}

export function resolveSelectedProjectId(
  projects: readonly Pick<BrowserProjectGrant, "id">[],
  storedProjectId: string | undefined,
): string | undefined {
  if (
    storedProjectId !== undefined &&
    projects.some((project) => project.id === storedProjectId)
  ) {
    return storedProjectId;
  }
  return projects.length === 1 ? projects[0]?.id : undefined;
}

export interface ProjectSelection {
  readonly projects: readonly BrowserProjectGrant[];
  readonly selectedProjectId?: string;
  clearProject(): void;
  selectProject(projectId: string): void;
}

export function useProjectSelection(): ProjectSelection {
  const session = useAuthentication().session;
  const workspaceKey = session === undefined ? undefined : projectSelectionWorkspaceKey(session);
  const storedProjectId = useWorkspaceStore((state) =>
    workspaceKey === undefined ? undefined : state.selectedProjectByWorkspace[workspaceKey],
  );
  const clearSelectedProject = useWorkspaceStore((state) => state.clearSelectedProject);
  const setSelectedProject = useWorkspaceStore((state) => state.setSelectedProject);
  const projects = useMemo(() => session?.projects ?? [], [session]);
  const selectedProjectId = resolveSelectedProjectId(projects, storedProjectId);

  useEffect(() => {
    if (
      workspaceKey !== undefined &&
      storedProjectId !== undefined &&
      selectedProjectId !== storedProjectId
    ) {
      clearSelectedProject(workspaceKey);
    }
  }, [clearSelectedProject, selectedProjectId, storedProjectId, workspaceKey]);

  const clearProject = useCallback(() => {
    if (workspaceKey !== undefined) {
      clearSelectedProject(workspaceKey);
    }
  }, [clearSelectedProject, workspaceKey]);

  const selectProject = useCallback(
    (projectId: string) => {
      if (
        workspaceKey === undefined ||
        !projects.some((project) => project.id === projectId)
      ) {
        throw new ProjectSelectionError();
      }
      setSelectedProject(workspaceKey, projectId);
    },
    [projects, setSelectedProject, workspaceKey],
  );

  return { clearProject, projects, selectedProjectId, selectProject };
}
