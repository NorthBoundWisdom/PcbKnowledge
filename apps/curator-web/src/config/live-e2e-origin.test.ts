import { describe, expect, it } from "vitest";

import {
  isLoopbackHttpUrl,
  liveE2eBaseUrlVariable,
  resolveLiveE2eBaseUrl,
} from "./live-e2e-origin";

describe("live E2E credential boundary", () => {
  it("is disabled when the opt-in variable is absent", () => {
    expect(resolveLiveE2eBaseUrl({})).toBeUndefined();
  });

  it.each(["http://localhost:18080", "http://127.0.0.1:8080/"])(
    "accepts the exact local origin %s",
    (origin) => {
      expect(resolveLiveE2eBaseUrl({ [liveE2eBaseUrlVariable]: origin })).toBe(
        new URL(origin).origin,
      );
    },
  );

  it.each([
    "",
    "https://localhost:18080",
    "http://example.test:18080",
    "http://localhost",
    "http://localhost:0",
    "http://localhost:65536",
    "http://localhost:18080/path",
    "http://user@localhost:18080",
    "http://localhost:18080.evil.invalid",
  ])("rejects a non-local or ambiguous live origin", (origin) => {
    expect(() =>
      resolveLiveE2eBaseUrl({ [liveE2eBaseUrlVariable]: origin }),
    ).toThrow(/exact loopback HTTP origin/u);
  });

  it("accepts only a loopback HTTP login URL with an explicit port", () => {
    expect(isLoopbackHttpUrl("http://localhost:18081/realms/pcbknowledge/login-actions/authenticate"))
      .toBe(true);
    expect(isLoopbackHttpUrl("https://localhost:18081/realms/pcbknowledge")).toBe(false);
    expect(isLoopbackHttpUrl("http://identity.example.test:18081/realms/pcbknowledge")).toBe(false);
  });
});
