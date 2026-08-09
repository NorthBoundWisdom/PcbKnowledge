import { afterEach, describe, expect, it, vi } from "vitest";

import type { UploadSessionProjection } from "./upload-polling";
import { pollUploadSession } from "./upload-polling";

function projection(state: UploadSessionProjection["state"]): UploadSessionProjection {
  return {
    created_at: "2026-08-09T10:00:00Z",
    document_id: "00000000-0000-7000-8000-000000000031",
    id: "00000000-0000-7000-8000-000000000032",
    project_id: "00000000-0000-7000-8000-000000000021",
    replayed: false,
    revision_id: "00000000-0000-7000-8000-000000000033",
    state,
    updated_at: "2026-08-09T10:00:00Z",
  };
}

afterEach(() => vi.useRealTimers());

describe("pollUploadSession", () => {
  it("polls until the server reports a terminal state", async () => {
    vi.useFakeTimers();
    const load = vi
      .fn<() => Promise<UploadSessionProjection>>()
      .mockResolvedValueOnce(projection("QUEUED"))
      .mockResolvedValueOnce(projection("VERIFYING"))
      .mockResolvedValueOnce(projection("STORED"));
    const controller = new AbortController();
    const result = pollUploadSession({ intervalMilliseconds: 10, load, signal: controller.signal });

    await vi.advanceTimersByTimeAsync(20);

    await expect(result).resolves.toMatchObject({ state: "STORED" });
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("cleans up the timer and stops loading after abort", async () => {
    vi.useFakeTimers();
    const load = vi.fn(() => Promise.resolve(projection("QUEUED")));
    const controller = new AbortController();
    const result = pollUploadSession({ intervalMilliseconds: 1_000, load, signal: controller.signal });
    await vi.advanceTimersByTimeAsync(0);

    controller.abort();
    await expect(result).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(2_000);

    expect(load).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });
});
