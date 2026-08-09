import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { z } from "zod";

import { useApiClientBoundary } from "../../api/client-boundary-context";
import { useAuthentication } from "../../auth/use-authentication";
import { useWorkspaceStore } from "../../state/workspace-store";
import { formatTimestamp } from "../shared/format";
import { FeatureRequestError, runGeneratedRequest, toRouteFailureKind } from "../shared/generated-request";
import { curatorQueryKeys } from "../shared/query-keys";
import { navigateToAuthorizedOriginal } from "./authorized-original-navigation";
import {
  DocumentRevisionPageView,
  type DocumentRevisionViewState,
} from "./DocumentRevisionPageView";

export function DocumentRevisionPage() {
  const api = useApiClientBoundary();
  const auth = useAuthentication();
  const parameters = useParams<{ revisionId: string }>();
  const parsedRevisionId = z.uuidv7().safeParse(parameters.revisionId);
  const revisionId = parsedRevisionId.success ? parsedRevisionId.data : undefined;
  const rememberProjectLabels = useWorkspaceStore((state) => state.rememberProjectLabels);
  const query = useQuery({
    enabled: revisionId !== undefined && auth.session !== undefined,
    queryFn: () =>
      runGeneratedRequest(
        () =>
          api.transport.GET("/document-revisions/{revision_id}", {
            params: { path: { revision_id: revisionId ?? "" } },
          }),
        auth.invalidateSession,
      ),
    queryKey: curatorQueryKeys.document(auth.session, revisionId),
    retry: false,
  });
  const download = useMutation({
    mutationFn: async () => {
      if (revisionId === undefined) throw new FeatureRequestError("not_found");
      const authorized = await runGeneratedRequest(
        () =>
          api.transport.POST("/document-revisions/{revision_id}/original-download", {
            params: { path: { revision_id: revisionId } },
          }),
        auth.invalidateSession,
      );
      navigateToAuthorizedOriginal(authorized.url);
    },
  });

  useEffect(() => {
    if (query.data !== undefined) {
      rememberProjectLabels([
        { id: query.data.project.id, label: query.data.project.display_name },
      ]);
    }
  }, [query.data, rememberProjectLabels]);

  let state: DocumentRevisionViewState;
  if (revisionId === undefined) {
    state = { kind: "not_found", status: "failed" };
  } else if (query.isError) {
    state = {
      kind: toRouteFailureKind(query.error),
      onRetry: () => void query.refetch(),
      status: "failed",
    };
  } else if (query.isPending || query.data === undefined) {
    state = { status: "loading" };
  } else {
    state = {
      revision: {
        byteSize: query.data.byte_size,
        createdAt: formatTimestamp(query.data.created_at),
        documentId: query.data.document_id,
        documentNumber: query.data.document_number ?? undefined,
        id: query.data.id,
        mediaType: query.data.media_type,
        originalFilename: query.data.original_filename,
        projectName: query.data.project.display_name,
        revisionLabel: query.data.revision_label,
        sha256: query.data.sha256,
        sourceOrganizationName: query.data.source_organization.name,
        state: query.data.state,
        title: query.data.title,
      },
      status: "ready",
    };
  }

  return (
    <DocumentRevisionPageView
      download={{ status: download.isPending ? "authorizing" : download.isError ? "failed" : "idle" }}
      onDownload={() => download.mutate()}
      state={state}
    />
  );
}
