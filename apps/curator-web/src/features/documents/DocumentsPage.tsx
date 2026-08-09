import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import type { components } from "../../api/generated";
import { useApiClientBoundary } from "../../api/client-boundary-context";
import { useAuthentication } from "../../auth/use-authentication";
import { useWorkspaceStore } from "../../state/workspace-store";
import { formatTimestamp } from "../shared/format";
import { runGeneratedRequest, toRouteFailureKind } from "../shared/generated-request";
import { curatorQueryKeys } from "../shared/query-keys";
import { useProjectSelection } from "../workspace/use-project-selection";
import { DocumentsPageView, type DocumentListViewState } from "./DocumentsPageView";

type DocumentListResponse = components["schemas"]["DocumentListResponse"];

export function DocumentsPage() {
  const api = useApiClientBoundary();
  const auth = useAuthentication();
  const project = useProjectSelection();
  const selectedProjectId = project.selectedProjectId;
  const rememberProjectLabels = useWorkspaceStore((state) => state.rememberProjectLabels);
  const query = useInfiniteQuery({
    enabled: selectedProjectId !== undefined,
    getNextPageParam: (lastPage: DocumentListResponse) => lastPage.next_cursor ?? undefined,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }): Promise<DocumentListResponse> => {
      if (selectedProjectId === undefined) {
        throw new Error("Document query cannot run without a trusted project selection");
      }
      return runGeneratedRequest(
        () =>
          api.transport.GET("/documents", {
            params: {
              query: {
                cursor: pageParam,
                limit: 25,
                project_id: selectedProjectId,
              },
            },
          }),
        auth.invalidateSession,
      );
    },
    queryKey: curatorQueryKeys.documents(auth.session, selectedProjectId),
    retry: false,
  });
  const items = useMemo(
    () =>
      query.data?.pages.flatMap((page) =>
        page.items.map((item) => ({
          documentId: item.id,
          documentNumber: item.document_number ?? undefined,
          projectName: item.project.display_name,
          revisionCreatedAt: formatTimestamp(item.latest_revision.created_at),
          revisionId: item.latest_revision.id,
          revisionLabel: item.latest_revision.revision_label,
          state: item.latest_revision.state,
          title: item.title,
        })),
      ) ?? [],
    [query.data],
  );

  useEffect(() => {
    const labels = query.data?.pages.flatMap((page) =>
      page.items.map((item) => ({ id: item.project.id, label: item.project.display_name })),
    );
    if (labels !== undefined) rememberProjectLabels(labels);
  }, [query.data, rememberProjectLabels]);

  let state: DocumentListViewState;
  if (query.isError) {
    state = {
      kind: toRouteFailureKind(query.error),
      onRetry: () => void query.refetch(),
      status: "failed",
    };
  } else if (query.isPending) {
    state = { status: "loading" };
  } else {
    state = {
      hasNextPage: query.hasNextPage,
      items,
      loadingNextPage: query.isFetchingNextPage,
      onLoadNextPage: () => void query.fetchNextPage(),
      status: "ready",
    };
  }

  return (
    <DocumentsPageView
      projectSelected={selectedProjectId !== undefined}
      state={state}
    />
  );
}
