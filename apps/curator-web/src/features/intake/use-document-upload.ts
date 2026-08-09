import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { components } from "../../api/generated";
import { useApiClientBoundary } from "../../api/client-boundary-context";
import { useAuthentication } from "../../auth/use-authentication";
import { useWorkspaceStore } from "../../state/workspace-store";
import { FeatureRequestError, runGeneratedRequest } from "../shared/generated-request";
import { curatorQueryKeys } from "../shared/query-keys";
import { PresignedUploadAbortedError, PresignedUploadError, putPresignedPdf } from "./presigned-upload";
import type {
  IntakeFormSubmission,
  UploadActivity,
  UploadFailureKind,
} from "./intake-view-models";
import { pollUploadSession, type UploadSessionProjection } from "./upload-polling";

type CreateUploadSessionRequest = components["schemas"]["CreateUploadSessionRequest"];

interface UploadAttempt {
  readonly file: File;
  readonly fingerprint: string;
  readonly idempotencyKey: string;
}

function submissionFingerprint(submission: IntakeFormSubmission): string {
  return JSON.stringify({
    accessScopeId: submission.accessScopeId,
    documentNumber: submission.documentNumber,
    file: {
      lastModified: submission.file.lastModified,
      name: submission.file.name,
      size: submission.file.size,
      type: submission.file.type,
    },
    licensePolicyId: submission.licensePolicyId,
    projectId: submission.projectId,
    revisionLabel: submission.revisionLabel,
    sourceOrganizationId: submission.sourceOrganizationId,
    title: submission.title,
  });
}

function failureKind(error: unknown): UploadFailureKind {
  if (error instanceof FeatureRequestError) {
    if (error.kind === "conflict") return "conflict";
    if (error.kind === "file_rejected") return "file_rejected";
    if (error.kind === "forbidden" || error.kind === "not_found") return "forbidden";
    if (error.kind === "service_unavailable") return "service_unavailable";
    if (error.kind === "network") return "network";
  }
  if (error instanceof PresignedUploadError) return "network";
  return "unexpected";
}

function isAbort(error: unknown): boolean {
  return (
    error instanceof PresignedUploadAbortedError ||
    (error instanceof DOMException && error.name === "AbortError")
  );
}

export interface DocumentUploadController {
  readonly activity: UploadActivity;
  submit(submission: IntakeFormSubmission): void;
}

export function useDocumentUpload(): DocumentUploadController {
  const api = useApiClientBoundary();
  const auth = useAuthentication();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const upsertRecentUpload = useWorkspaceStore((state) => state.upsertRecentUpload);
  const [activity, setActivity] = useState<UploadActivity>({ phase: "idle" });
  const controllerRef = useRef<AbortController | null>(null);
  const attemptRef = useRef<UploadAttempt | null>(null);
  const workspaceKey =
    auth.session === undefined
      ? undefined
      : `${auth.session.subjectId}:${auth.session.organizationId}`;

  useEffect(
    () => () => {
      controllerRef.current?.abort();
      controllerRef.current = null;
    },
    [],
  );

  const submit = useCallback(
    (submission: IntakeFormSubmission) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      const fingerprint = submissionFingerprint(submission);
      if (
        attemptRef.current?.file !== submission.file ||
        attemptRef.current.fingerprint !== fingerprint
      ) {
        attemptRef.current = {
          file: submission.file,
          fingerprint,
          idempotencyKey: `curator-${crypto.randomUUID()}`,
        };
      }
      const attempt = attemptRef.current;

      const isActive = () => controllerRef.current === controller && !controller.signal.aborted;
      const updateActivity = (next: UploadActivity) => {
        if (isActive()) setActivity(next);
      };
      const remember = (session: UploadSessionProjection) => {
        if (workspaceKey === undefined) return;
        upsertRecentUpload(workspaceKey, {
          failureCode: session.failure_code ?? undefined,
          id: session.id,
          revisionId: session.revision_id,
          state: session.state,
          title: submission.title,
          updatedAt: session.updated_at,
        });
      };
      const finishStored = async (session: UploadSessionProjection) => {
        remember(session);
        attemptRef.current = null;
        updateActivity({ phase: "available" });
        await queryClient.invalidateQueries({
          queryKey: curatorQueryKeys.documents(auth.session, session.project_id),
        });
        if (isActive()) navigate(`/documents/${session.revision_id}`);
      };
      const finishFailed = (session: UploadSessionProjection) => {
        remember(session);
        attemptRef.current = null;
        updateActivity({ failure: "verification_failed", phase: "failed" });
      };

      void (async () => {
        try {
          updateActivity({ phase: "reserving" });
          const requestBody = {
            access_scope_id: submission.accessScopeId,
            byte_size: submission.file.size,
            document_number: submission.documentNumber,
            license_policy_id: submission.licensePolicyId,
            media_type: "application/pdf",
            original_filename: submission.file.name,
            project_id: submission.projectId,
            revision_label: submission.revisionLabel,
            source_organization_id: submission.sourceOrganizationId,
            title: submission.title,
          } satisfies CreateUploadSessionRequest;
          let session = await runGeneratedRequest(
            () =>
              api.transport.POST("/upload-sessions", {
                body: requestBody,
                params: { header: { "Idempotency-Key": attempt.idempotencyKey } },
                signal: controller.signal,
              }),
            auth.invalidateSession,
          );
          remember(session);

          if (session.state === "FAILED") {
            finishFailed(session);
            return;
          }
          if (session.state === "STORED") {
            await finishStored(session);
            return;
          }
          if (session.state === "RESERVED") {
            if (session.upload === undefined || session.upload === null) {
              throw new FeatureRequestError("unexpected");
            }
            updateActivity({ percent: 0, phase: "uploading" });
            await putPresignedPdf(session.upload, submission.file, {
              onProgress: ({ percent }) => updateActivity({ percent, phase: "uploading" }),
              signal: controller.signal,
            });
            updateActivity({ phase: "completing" });
            session = await runGeneratedRequest(
              () =>
                api.transport.POST("/upload-sessions/{upload_session_id}/complete", {
                  body: {},
                  params: { path: { upload_session_id: session.id } },
                  signal: controller.signal,
                }),
              auth.invalidateSession,
            );
            remember(session);
          }

          if (session.state === "FAILED") {
            finishFailed(session);
            return;
          }
          if (session.state === "STORED") {
            await finishStored(session);
            return;
          }
          updateActivity({ phase: "verifying" });
          const terminal = await pollUploadSession({
            load: () =>
              runGeneratedRequest(
                () =>
                  api.transport.GET("/upload-sessions/{upload_session_id}", {
                    params: { path: { upload_session_id: session.id } },
                    signal: controller.signal,
                  }),
                auth.invalidateSession,
              ),
            onUpdate: remember,
            signal: controller.signal,
          });
          if (terminal.state === "STORED") {
            await finishStored(terminal);
          } else {
            finishFailed(terminal);
          }
        } catch (error) {
          if (isAbort(error) || !isActive()) return;
          updateActivity({ failure: failureKind(error), phase: "failed" });
        } finally {
          if (controllerRef.current === controller) {
            controllerRef.current = null;
          }
        }
      })();
    },
    [
      api.transport,
      auth.invalidateSession,
      auth.session,
      navigate,
      queryClient,
      upsertRecentUpload,
      workspaceKey,
    ],
  );

  return { activity, submit };
}
