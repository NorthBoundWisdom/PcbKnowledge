import { useQueries } from "@tanstack/react-query";
import { useEffect } from "react";

import { useApiClientBoundary } from "../../api/client-boundary-context";
import { useAuthentication } from "../../auth/use-authentication";
import { useWorkspaceStore } from "../../state/workspace-store";
import { formatTimestamp } from "../shared/format";
import { runGeneratedRequest } from "../shared/generated-request";
import { curatorQueryKeys } from "../shared/query-keys";
import { IntakeInboxPageView } from "./IntakeInboxPageView";

const terminalStates = new Set(["FAILED", "STORED"]);
const emptyRecentUploads = [] as const;

export function IntakeInboxPage() {
  const api = useApiClientBoundary();
  const auth = useAuthentication();
  const workspaceKey =
    auth.session === undefined
      ? undefined
      : `${auth.session.subjectId}:${auth.session.organizationId}`;
  const recentUploads = useWorkspaceStore((state) =>
    workspaceKey === undefined
      ? emptyRecentUploads
      : (state.recentUploadsByWorkspace[workspaceKey] ?? emptyRecentUploads),
  );
  const upsertRecentUpload = useWorkspaceStore((state) => state.upsertRecentUpload);
  const queries = useQueries({
    queries: recentUploads.map((upload) => ({
      queryFn: () =>
        runGeneratedRequest(
          () =>
            api.transport.GET("/upload-sessions/{upload_session_id}", {
              params: { path: { upload_session_id: upload.id } },
            }),
          auth.invalidateSession,
        ),
      queryKey: curatorQueryKeys.uploadSession(auth.session, upload.id),
      refetchInterval: (query: { state: { data?: { state: string } } }) =>
        query.state.data !== undefined && terminalStates.has(query.state.data.state) ? false : 1_000,
      retry: false,
    })),
  });

  useEffect(() => {
    if (workspaceKey === undefined) return;
    for (const [index, query] of queries.entries()) {
      const session = query.data;
      const prior = recentUploads[index];
      if (session === undefined || prior === undefined) continue;
      if (
        prior.failureCode === (session.failure_code ?? undefined) &&
        prior.revisionId === session.revision_id &&
        prior.state === session.state &&
        prior.updatedAt === session.updated_at
      ) {
        continue;
      }
      upsertRecentUpload(workspaceKey, {
        failureCode: session.failure_code ?? undefined,
        id: session.id,
        revisionId: session.revision_id,
        state: session.state,
        title: prior.title,
        updatedAt: session.updated_at,
      });
    }
  }, [queries, recentUploads, upsertRecentUpload, workspaceKey]);

  const items = recentUploads.map((upload, index) => ({
    ...upload,
    state: queries[index]?.isError === true ? "UNAVAILABLE" : upload.state,
    updatedAt: formatTimestamp(upload.updatedAt),
  }));
  return <IntakeInboxPageView items={items} />;
}
