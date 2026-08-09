import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export interface RecentUploadSummary {
  readonly failureCode?: string;
  readonly id: string;
  readonly revisionId: string;
  readonly state: string;
  readonly title: string;
  readonly updatedAt: string;
}

interface WorkspaceState {
  projectLabelsById: Readonly<Record<string, string>>;
  recentUploadsByWorkspace: Readonly<Record<string, readonly RecentUploadSummary[]>>;
  selectedProjectByWorkspace: Readonly<Record<string, string>>;
  clearSelectedProject: (workspaceKey: string) => void;
  rememberProjectLabels: (
    projects: readonly { readonly id: string; readonly label: string }[],
  ) => void;
  setSelectedProject: (workspaceKey: string, projectId: string) => void;
  upsertRecentUpload: (workspaceKey: string, upload: RecentUploadSummary) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      clearSelectedProject: (workspaceKey) =>
        set((state) => {
          const remainingSelections = { ...state.selectedProjectByWorkspace };
          delete remainingSelections[workspaceKey];
          return { selectedProjectByWorkspace: remainingSelections };
        }),
      projectLabelsById: {},
      recentUploadsByWorkspace: {},
      rememberProjectLabels: (projects) =>
        set((state) => ({
          projectLabelsById: {
            ...state.projectLabelsById,
            ...Object.fromEntries(projects.map((project) => [project.id, project.label])),
          },
        })),
      selectedProjectByWorkspace: {},
      setSelectedProject: (workspaceKey, projectId) =>
        set((state) => ({
          selectedProjectByWorkspace: {
            ...state.selectedProjectByWorkspace,
            [workspaceKey]: projectId,
          },
        })),
      upsertRecentUpload: (workspaceKey, upload) =>
        set((state) => ({
          recentUploadsByWorkspace: {
            ...state.recentUploadsByWorkspace,
            [workspaceKey]: [
              upload,
              ...(state.recentUploadsByWorkspace[workspaceKey] ?? []).filter(
                (candidate) => candidate.id !== upload.id,
              ),
            ].slice(0, 20),
          },
        })),
    }),
    {
      name: "pcbknowledge-curator-workspace-v1",
      partialize: ({ selectedProjectByWorkspace }) => ({ selectedProjectByWorkspace }),
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
