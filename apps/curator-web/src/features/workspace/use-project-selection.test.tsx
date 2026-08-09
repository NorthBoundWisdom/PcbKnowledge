import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { AppProviders } from "../../app/AppProviders";
import {
  createHumanUser,
  createTrustedSession,
  FakeAuthClient,
} from "../../test/fake-auth-client";
import { validRuntimeConfig } from "../../test/test-config";
import { useWorkspaceStore } from "../../state/workspace-store";
import {
  ProjectSelectionError,
  projectSelectionWorkspaceKey,
  resolveSelectedProjectId,
  useProjectSelection,
} from "./use-project-selection";

const projectOne = "00000000-0000-7000-8000-000000000021";
const projectTwo = "00000000-0000-7000-8000-000000000022";

function wrapper(projectIds: string[]) {
  const authClient = new FakeAuthClient(createHumanUser(["DATA_CURATOR"]));
  const session = createTrustedSession(
    [],
    projectIds.map((id) => ({ id, roles: ["DATA_CURATOR"] })),
  );
  return function TestWrapper({ children }: PropsWithChildren) {
    return (
      <AppProviders
        authClient={authClient}
        config={validRuntimeConfig}
        loadTrustedSession={() => Promise.resolve(session)}
      >
        {children}
      </AppProviders>
    );
  };
}

describe("project selection", () => {
  beforeEach(() => {
    useWorkspaceStore.setState({ selectedProjectByWorkspace: {} });
  });

  it("uses the only trusted project without requiring a persisted choice", async () => {
    const { result } = renderHook(() => useProjectSelection(), {
      wrapper: wrapper([projectOne]),
    });

    await waitFor(() => expect(result.current.selectedProjectId).toBe(projectOne));
  });

  it("selects only a project present in the trusted session", async () => {
    const { result } = renderHook(() => useProjectSelection(), {
      wrapper: wrapper([projectOne, projectTwo]),
    });

    await waitFor(() => expect(result.current.projects).toHaveLength(2));
    expect(result.current.selectedProjectId).toBeUndefined();

    act(() => result.current.selectProject(projectTwo));

    expect(result.current.selectedProjectId).toBe(projectTwo);
    expect(() => result.current.selectProject("00000000-0000-7000-8000-000000000099")).toThrow(
      ProjectSelectionError,
    );
  });

  it("fails closed when a stored project is no longer granted", () => {
    expect(resolveSelectedProjectId([{ id: projectOne }], projectTwo)).toBe(projectOne);
    expect(
      resolveSelectedProjectId([{ id: projectOne }, { id: projectTwo }], "revoked"),
    ).toBeUndefined();
  });

  it("separates persisted selections by human and organization", () => {
    expect(
      projectSelectionWorkspaceKey({
        organizationId: "00000000-0000-7000-8000-000000000010",
        subjectId: "00000000-0000-7000-8000-000000000011",
      }),
    ).not.toBe(
      projectSelectionWorkspaceKey({
        organizationId: "00000000-0000-7000-8000-000000000010",
        subjectId: "00000000-0000-7000-8000-000000000012",
      }),
    );
  });
});
