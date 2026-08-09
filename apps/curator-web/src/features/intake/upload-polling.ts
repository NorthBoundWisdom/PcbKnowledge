import type { components } from "../../api/generated";

export type UploadSessionProjection = components["schemas"]["UploadSessionResponse"];

interface PollUploadSessionOptions {
  readonly intervalMilliseconds?: number;
  readonly load: () => Promise<UploadSessionProjection>;
  readonly onUpdate?: (session: UploadSessionProjection) => void;
  readonly signal: AbortSignal;
}

function waitForNextPoll(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Polling aborted", "AbortError"));
      return;
    }
    const timeout = window.setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, milliseconds);
    const abort = () => {
      window.clearTimeout(timeout);
      reject(new DOMException("Polling aborted", "AbortError"));
    };
    signal.addEventListener("abort", abort, { once: true });
  });
}

export async function pollUploadSession({
  intervalMilliseconds = 1_000,
  load,
  onUpdate,
  signal,
}: PollUploadSessionOptions): Promise<UploadSessionProjection> {
  while (true) {
    if (signal.aborted) {
      throw new DOMException("Polling aborted", "AbortError");
    }
    const session = await load();
    onUpdate?.(session);
    if (session.state === "STORED" || session.state === "FAILED") {
      return session;
    }
    await waitForNextPoll(intervalMilliseconds, signal);
  }
}
