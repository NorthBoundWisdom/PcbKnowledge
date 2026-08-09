export interface PresignedUploadTarget {
  readonly headers: Readonly<Record<string, string>>;
  readonly url: string;
}

export interface UploadProgress {
  readonly loadedBytes: number;
  readonly percent?: number;
  readonly totalBytes?: number;
}

export class PresignedUploadError extends Error {
  constructor(message = "The PDF could not be uploaded to staging storage") {
    super(message);
    this.name = "PresignedUploadError";
  }
}

export class PresignedUploadAbortedError extends PresignedUploadError {
  constructor() {
    super("The staging upload was cancelled");
    this.name = "PresignedUploadAbortedError";
  }
}

export class PresignedUploadConfigurationError extends PresignedUploadError {
  constructor() {
    super("The staging upload target contained an unsafe browser header or URL");
    this.name = "PresignedUploadConfigurationError";
  }
}

function validateTarget(target: PresignedUploadTarget): string {
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(target.url);
  } catch {
    throw new PresignedUploadConfigurationError();
  }
  if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
    throw new PresignedUploadConfigurationError();
  }
  let contentType: string | undefined;
  for (const [name, value] of Object.entries(target.headers)) {
    const normalizedName = name.trim().toLowerCase();
    if (
      normalizedName !== "content-type" ||
      contentType !== undefined ||
      /[\r\n]/u.test(name) ||
      /[\r\n]/u.test(value)
    ) {
      throw new PresignedUploadConfigurationError();
    }
    contentType = value;
  }
  if (contentType !== "application/pdf") {
    throw new PresignedUploadConfigurationError();
  }
  return contentType;
}

export interface PutPresignedPdfOptions {
  readonly createRequest?: () => XMLHttpRequest;
  readonly onProgress?: (progress: UploadProgress) => void;
  readonly signal?: AbortSignal;
}

/**
 * Uploads only to the one-time object-store URL returned by the API.
 * This transport is deliberately separate from the generated Bearer API client.
 */
export function putPresignedPdf(
  target: PresignedUploadTarget,
  file: File,
  options: PutPresignedPdfOptions = {},
): Promise<void> {
  const contentType = validateTarget(target);
  const request = (options.createRequest ?? (() => new XMLHttpRequest()))();

  return new Promise((resolve, reject) => {
    let settled = false;

    const finish = (result: "aborted" | "failed" | "succeeded") => {
      if (settled) {
        return;
      }
      settled = true;
      options.signal?.removeEventListener("abort", abort);
      if (result === "succeeded") {
        resolve();
      } else if (result === "aborted") {
        reject(new PresignedUploadAbortedError());
      } else {
        reject(new PresignedUploadError());
      }
    };
    const abort = () => request.abort();

    if (options.signal?.aborted === true) {
      finish("aborted");
      return;
    }
    options.signal?.addEventListener("abort", abort, { once: true });

    request.open("PUT", target.url, true);
    request.withCredentials = false;
    request.setRequestHeader("Content-Type", contentType);
    request.upload.onprogress = (event) => {
      const hasTotal = event.lengthComputable && event.total > 0;
      options.onProgress?.({
        loadedBytes: event.loaded,
        percent: hasTotal ? Math.min(100, Math.round((event.loaded / event.total) * 100)) : undefined,
        totalBytes: hasTotal ? event.total : undefined,
      });
    };
    request.onerror = () => finish("failed");
    request.onabort = () => finish("aborted");
    request.onload = () =>
      finish(request.status >= 200 && request.status < 300 ? "succeeded" : "failed");
    request.send(file);
  });
}
