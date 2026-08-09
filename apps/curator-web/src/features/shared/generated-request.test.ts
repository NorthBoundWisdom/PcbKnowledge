import { describe, expect, it, vi } from "vitest";

import { BrowserAuthenticationRequiredError } from "../../api/client-boundary";
import { FeatureRequestError, runGeneratedRequest } from "./generated-request";

describe("runGeneratedRequest", () => {
  it("returns generated response data", async () => {
    await expect(
      runGeneratedRequest(
        () => Promise.resolve({ data: { value: "typed" }, response: new Response(null, { status: 200 }) }),
        vi.fn(),
      ),
    ).resolves.toEqual({ value: "typed" });
  });

  it("invalidates the in-memory session on a 401", async () => {
    const invalidateSession = vi.fn(() => Promise.resolve());

    await expect(
      runGeneratedRequest(
        () => Promise.resolve({ response: new Response(null, { status: 401 }) }),
        invalidateSession,
      ),
    ).rejects.toMatchObject({ kind: "session_expired", status: 401 });
    expect(invalidateSession).toHaveBeenCalledOnce();
  });

  it("invalidates when the generated Bearer boundary has no active user", async () => {
    const invalidateSession = vi.fn(() => Promise.resolve());

    await expect(
      runGeneratedRequest(
        () => Promise.reject(new BrowserAuthenticationRequiredError()),
        invalidateSession,
      ),
    ).rejects.toBeInstanceOf(FeatureRequestError);
    expect(invalidateSession).toHaveBeenCalledOnce();
  });

  it.each([
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
    [413, "file_rejected"],
    [503, "service_unavailable"],
  ] as const)("classifies HTTP %i without reflecting the response body", async (status, kind) => {
    await expect(
      runGeneratedRequest(
        () => Promise.resolve({ response: new Response("untrusted detail", { status }) }),
        vi.fn(),
      ),
    ).rejects.toMatchObject({ kind, status });
  });
});
