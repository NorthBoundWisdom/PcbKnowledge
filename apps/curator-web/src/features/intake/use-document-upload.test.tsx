import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../../api/generated";
import { useWorkspaceStore } from "../../state/workspace-store";
import type { IntakeFormSubmission } from "./intake-view-models";
import { useDocumentUpload } from "./use-document-upload";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  invalidateSession: vi.fn(() => Promise.resolve()),
  post: vi.fn(),
  putPresignedPdf: vi.fn(),
}));

vi.mock("../../api/client-boundary-context", () => ({
  useApiClientBoundary: () => ({ transport: { GET: mocks.get, POST: mocks.post } }),
}));

vi.mock("../../auth/use-authentication", () => ({
  useAuthentication: () => ({
    invalidateSession: mocks.invalidateSession,
    session: {
      organizationId: "00000000-0000-7000-8000-000000000010",
      subjectId: "00000000-0000-7000-8000-000000000011",
    },
  }),
}));

vi.mock("./presigned-upload", async (importOriginal) => {
  const original = await importOriginal<typeof import("./presigned-upload")>();
  return { ...original, putPresignedPdf: mocks.putPresignedPdf };
});

type UploadSession = components["schemas"]["UploadSessionResponse"];

const uploadId = "00000000-0000-7000-8000-000000000032";
const revisionId = "00000000-0000-7000-8000-000000000033";
const projectId = "00000000-0000-7000-8000-000000000021";

function uploadSession(
  state: UploadSession["state"],
  upload?: UploadSession["upload"],
): UploadSession {
  return {
    created_at: "2026-08-09T10:00:00Z",
    document_id: "00000000-0000-7000-8000-000000000031",
    id: uploadId,
    project_id: projectId,
    replayed: false,
    revision_id: revisionId,
    state,
    updated_at: "2026-08-09T10:00:00Z",
    upload,
  };
}

function generatedResult(data: UploadSession, status: number) {
  return Promise.resolve({ data, response: new Response(null, { status }) });
}

function wrapper({ children }: PropsWithChildren) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useWorkspaceStore.setState({ recentUploadsByWorkspace: {} });
});

describe("useDocumentUpload", () => {
  it("runs generated create, external PUT, generated complete, and polling in order", async () => {
    const file = new File(["%PDF-1.7\n%%EOF"], "reference.pdf", {
      type: "application/pdf",
    });
    const submission: IntakeFormSubmission = {
      accessScopeId: "00000000-0000-7000-8000-000000000022",
      documentNumber: "DS-100",
      file,
      licensePolicyId: "00000000-0000-7000-8000-000000000023",
      projectId,
      revisionLabel: "A",
      sourceOrganizationId: "00000000-0000-7000-8000-000000000024",
      title: "Reference Datasheet",
    };
    const target = {
      expires_in_seconds: 900,
      headers: { "Content-Type": "application/pdf" },
      url: "https://objects.example.test/private-one-time-target",
    };
    mocks.post
      .mockImplementationOnce(() => generatedResult(uploadSession("RESERVED", target), 201))
      .mockImplementationOnce(() => generatedResult(uploadSession("QUEUED"), 202));
    mocks.putPresignedPdf.mockImplementation(
      (_target: unknown, _file: unknown, options: { onProgress: (value: { percent: number }) => void }) => {
        options.onProgress({ percent: 60 });
        return Promise.resolve();
      },
    );
    mocks.get.mockImplementationOnce(() => generatedResult(uploadSession("STORED"), 200));
    const { result } = renderHook(() => useDocumentUpload(), { wrapper });

    act(() => result.current.submit(submission));
    await waitFor(() => expect(result.current.activity.phase).toBe("available"));

    expect(mocks.post.mock.calls[0]?.[0]).toBe("/upload-sessions");
    expect(mocks.post.mock.calls[0]?.[1]).toMatchObject({
      body: {
        access_scope_id: submission.accessScopeId,
        byte_size: file.size,
        document_number: "DS-100",
        license_policy_id: submission.licensePolicyId,
        media_type: "application/pdf",
        original_filename: "reference.pdf",
        project_id: projectId,
        revision_label: "A",
        source_organization_id: submission.sourceOrganizationId,
        title: "Reference Datasheet",
      },
      params: { header: { "Idempotency-Key": expect.stringMatching(/^curator-[0-9a-f-]+$/u) } },
    });
    expect(mocks.putPresignedPdf).toHaveBeenCalledWith(
      target,
      file,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(mocks.post.mock.calls[1]?.[0]).toBe(
      "/upload-sessions/{upload_session_id}/complete",
    );
    expect(mocks.get).toHaveBeenCalledWith(
      "/upload-sessions/{upload_session_id}",
      expect.objectContaining({ params: { path: { upload_session_id: uploadId } } }),
    );
    expect(mocks.invalidateSession).not.toHaveBeenCalled();
    expect(
      useWorkspaceStore.getState().recentUploadsByWorkspace[
        "00000000-0000-7000-8000-000000000011:00000000-0000-7000-8000-000000000010"
      ]?.[0],
    ).toMatchObject({ revisionId, state: "STORED", title: "Reference Datasheet" });
  });

  it("uses a new idempotency key for a reselected lookalike File after an uncertain complete", async () => {
    const fileOptions = { lastModified: 1234, type: "application/pdf" } as const;
    const firstFile = new File(["%PDF-A"], "lookalike.pdf", fileOptions);
    const reselectedFile = new File(["%PDF-B"], "lookalike.pdf", fileOptions);
    expect(reselectedFile).not.toBe(firstFile);
    expect(reselectedFile.size).toBe(firstFile.size);

    const submission: IntakeFormSubmission = {
      accessScopeId: "00000000-0000-7000-8000-000000000022",
      file: firstFile,
      licensePolicyId: "00000000-0000-7000-8000-000000000023",
      projectId,
      revisionLabel: "A",
      sourceOrganizationId: "00000000-0000-7000-8000-000000000024",
      title: "Lookalike idempotency regression",
    };
    const target = {
      expires_in_seconds: 900,
      headers: { "Content-Type": "application/pdf" },
      url: "https://objects.example.test/private-one-time-target",
    };
    mocks.post
      .mockImplementationOnce(() => generatedResult(uploadSession("RESERVED", target), 201))
      .mockRejectedValueOnce(new TypeError("complete response was lost"))
      .mockImplementationOnce(() => generatedResult(uploadSession("RESERVED", target), 201))
      .mockImplementationOnce(() => generatedResult(uploadSession("STORED"), 202));
    mocks.putPresignedPdf.mockResolvedValue(undefined);
    const { result } = renderHook(() => useDocumentUpload(), { wrapper });

    act(() => result.current.submit(submission));
    await waitFor(() => expect(result.current.activity.phase).toBe("failed"));

    act(() => result.current.submit({ ...submission, file: reselectedFile }));
    await waitFor(() => expect(result.current.activity.phase).toBe("available"));

    const firstKey = mocks.post.mock.calls[0]?.[1]?.params.header["Idempotency-Key"];
    const secondKey = mocks.post.mock.calls[2]?.[1]?.params.header["Idempotency-Key"];
    expect(firstKey).toMatch(/^curator-[0-9a-f-]+$/u);
    expect(secondKey).toMatch(/^curator-[0-9a-f-]+$/u);
    expect(secondKey).not.toBe(firstKey);
    expect(mocks.putPresignedPdf).toHaveBeenCalledTimes(2);
    expect(mocks.putPresignedPdf.mock.calls[1]?.[1]).toBe(reselectedFile);
  });
});
