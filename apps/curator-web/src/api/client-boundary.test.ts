import { afterEach, describe, expect, it, vi } from "vitest";

import { validRuntimeConfig } from "../test/test-config";
import {
  createHumanUser,
  createServiceUser,
  createTrustedSession,
  FakeAuthClient,
} from "../test/fake-auth-client";
import {
  BrowserAuthenticationRequiredError,
  createApiClientBoundary,
} from "./client-boundary";

const requestRuntimeConfig = {
  ...validRuntimeConfig,
  apiBaseUrl: "https://knowledge.example.test/api/v1",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("generated client boundary", () => {
  it("binds the generated paths contract without making a request", () => {
    const boundary = createApiClientBoundary(
      validRuntimeConfig,
      new FakeAuthClient(createHumanUser(["DATA_CURATOR"])),
    );

    expect(boundary.apiBaseUrl).toBe("/api/v1");
    expect(boundary.contractSha256).toMatch(/^[a-f0-9]{64}$/);
    expect(boundary.source).toBe("generated-openapi");
    expect(boundary.transport.GET).toBeTypeOf("function");
  });

  it("injects the current in-memory Bearer token through middleware", async () => {
    let receivedRequest: Request | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        receivedRequest = request;
        return new Response(
          JSON.stringify({ service: "pcbknowledge-api", status: "alive", version: "0.1.0" }),
          { headers: { "Content-Type": "application/json" }, status: 200 },
        );
      }),
    );
    const user = createHumanUser(["DATA_CURATOR"]);
    const boundary = createApiClientBoundary(requestRuntimeConfig, new FakeAuthClient(user));

    await boundary.transport.GET("/healthz");

    expect(receivedRequest?.headers.get("Authorization")).toBe(`Bearer ${user.access_token}`);
  });

  it("bootstraps the typed trusted session through the authenticated transport", async () => {
    let receivedRequest: Request | undefined;
    const trustedSession = createTrustedSession(["AUDITOR"]);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        receivedRequest = request;
        return new Response(JSON.stringify(trustedSession), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      }),
    );
    const user = createHumanUser(["KNOWLEDGE_ADMIN"]);
    const boundary = createApiClientBoundary(requestRuntimeConfig, new FakeAuthClient(user));

    await expect(boundary.loadTrustedSession()).resolves.toEqual(trustedSession);
    expect(receivedRequest?.url).toBe("https://knowledge.example.test/api/v1/session");
    expect(receivedRequest?.headers.get("Authorization")).toBe(`Bearer ${user.access_token}`);
  });

  it("rejects a request when no in-memory user exists", async () => {
    const boundary = createApiClientBoundary(requestRuntimeConfig, new FakeAuthClient());

    await expect(boundary.transport.GET("/healthz")).rejects.toBeInstanceOf(
      BrowserAuthenticationRequiredError,
    );
  });

  it("rejects an expired in-memory token before fetch", async () => {
    const user = createHumanUser(["DATA_CURATOR"]);
    user.expires_at = Math.floor(Date.now() / 1000) - 60;
    const boundary = createApiClientBoundary(requestRuntimeConfig, new FakeAuthClient(user));

    await expect(boundary.transport.GET("/healthz")).rejects.toBeInstanceOf(
      BrowserAuthenticationRequiredError,
    );
  });

  it("rejects a service identity before any browser request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const boundary = createApiClientBoundary(
      requestRuntimeConfig,
      new FakeAuthClient(createServiceUser()),
    );

    await expect(boundary.loadTrustedSession()).rejects.toBeInstanceOf(
      BrowserAuthenticationRequiredError,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
