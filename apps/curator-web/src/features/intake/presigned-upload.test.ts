import { describe, expect, it, vi } from "vitest";

import {
  PresignedUploadAbortedError,
  PresignedUploadConfigurationError,
  PresignedUploadError,
  putPresignedPdf,
} from "./presigned-upload";

class FakeRequest {
  readonly headers = new Map<string, string>();
  readonly upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
  method?: string;
  onabort: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onload: (() => void) | null = null;
  sentBody?: Document | XMLHttpRequestBodyInit | null;
  status = 200;
  url?: string;
  withCredentials = true;

  abort() {
    this.onabort?.();
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  send(body?: Document | XMLHttpRequestBodyInit | null) {
    this.sentBody = body;
  }

  setRequestHeader(name: string, value: string) {
    this.headers.set(name.toLowerCase(), value);
  }
}

function pdf(): File {
  return new File(["%PDF-1.7\n%%EOF"], "sample.pdf", { type: "application/pdf" });
}

function requestFactory(request: FakeRequest): () => XMLHttpRequest {
  return () => request as unknown as XMLHttpRequest;
}

describe("putPresignedPdf", () => {
  it("uploads with only signed storage headers and reports progress", async () => {
    const request = new FakeRequest();
    const onProgress = vi.fn();
    const result = putPresignedPdf(
      {
        headers: { "Content-Type": "application/pdf" },
        url: "https://objects.example.test/staging/upload?signature=test",
      },
      pdf(),
      { createRequest: requestFactory(request), onProgress },
    );

    request.upload.onprogress?.(
      new ProgressEvent("progress", { lengthComputable: true, loaded: 5, total: 10 }),
    );
    request.onload?.();
    await expect(result).resolves.toBeUndefined();

    expect(request.method).toBe("PUT");
    expect(request.withCredentials).toBe(false);
    expect(request.headers.get("content-type")).toBe("application/pdf");
    expect(request.headers.has("authorization")).toBe(false);
    expect(request.headers.has("content-length")).toBe(false);
    expect(request.sentBody).toBeInstanceOf(File);
    expect(onProgress).toHaveBeenCalledWith({ loadedBytes: 5, percent: 50, totalBytes: 10 });
  });

  it.each(["Authorization", "Content-Length", "Cookie", "x-amz-meta-example"])(
    "rejects an unsafe %s header before opening a request",
    async (header) => {
      const request = new FakeRequest();

      expect(() =>
        putPresignedPdf(
          { headers: { [header]: "unsafe" }, url: "https://objects.example.test/upload" },
          pdf(),
          { createRequest: requestFactory(request) },
        ),
      ).toThrow(PresignedUploadConfigurationError);
      expect(request.method).toBeUndefined();
    },
  );

  it("rejects a non-success storage response", async () => {
    const request = new FakeRequest();
    request.status = 403;
    const result = putPresignedPdf(
      { headers: { "Content-Type": "application/pdf" }, url: "https://objects.example.test/upload" },
      pdf(),
      { createRequest: requestFactory(request) },
    );

    request.onload?.();

    await expect(result).rejects.toBeInstanceOf(PresignedUploadError);
  });

  it("aborts without completing the upload", async () => {
    const request = new FakeRequest();
    const controller = new AbortController();
    const result = putPresignedPdf(
      { headers: { "Content-Type": "application/pdf" }, url: "https://objects.example.test/upload" },
      pdf(),
      { createRequest: requestFactory(request), signal: controller.signal },
    );

    controller.abort();

    await expect(result).rejects.toBeInstanceOf(PresignedUploadAbortedError);
  });
});
