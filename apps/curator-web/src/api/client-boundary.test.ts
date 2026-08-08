import { describe, expect, it } from "vitest";

import { validRuntimeConfig } from "../test/test-config";
import { createApiClientBoundary } from "./client-boundary";

describe("generated client boundary", () => {
  it("binds the generated paths contract without making a request", () => {
    const boundary = createApiClientBoundary(validRuntimeConfig);

    expect(boundary.apiBaseUrl).toBe("/api/v1");
    expect(boundary.contractSha256).toMatch(/^[a-f0-9]{64}$/);
    expect(boundary.source).toBe("generated-openapi");
    expect(boundary.transport.GET).toBeTypeOf("function");
  });
});
