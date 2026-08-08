import { describe, expect, it } from "vitest";

import { validRuntimeConfig } from "../test/test-config";
import {
  createHumanUser,
  createServiceUser,
  createTrustedSession,
} from "../test/fake-auth-client";
import { BrowserIdentityError, resolveBrowserSession } from "./auth-types";
import { createOidcSettings, oidcTransactionStoragePrefix } from "./oidc-client";

describe("OIDC client policy", () => {
  it("uses code + PKCE with transient transaction state and in-memory user storage", async () => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    const settings = createOidcSettings(
      validRuntimeConfig,
      "https://knowledge.example.test",
      window.sessionStorage,
    );

    expect(settings.response_type).toBe("code");
    expect(settings.response_mode).toBe("fragment");
    expect(settings.disablePKCE).toBe(false);
    expect(settings.redirect_uri).toBe("https://knowledge.example.test/auth/callback");
    expect(settings.staleStateAgeInSeconds).toBe(300);

    await settings.stateStore?.set("authorization-request", "pkce-verifier-and-state-only");
    await settings.userStore?.set(
      "authenticated-user",
      '{"access_token":"must-remain-in-memory","refresh_token":"must-remain-in-memory"}',
    );

    const transactionKeys = Object.keys(window.sessionStorage).filter((key) =>
      key.startsWith(oidcTransactionStoragePrefix),
    );
    expect(transactionKeys).toHaveLength(1);
    const persistedTransaction = transactionKeys
      .map((key) => window.sessionStorage.getItem(key) ?? "")
      .join("\n");
    expect(persistedTransaction).not.toMatch(/access_token|refresh_token/);
    expect(Object.keys(window.localStorage)).toHaveLength(0);
    expect(JSON.stringify(window.sessionStorage)).not.toContain("must-remain-in-memory");
  });

  it("derives capabilities only from the trusted session projection", () => {
    const session = resolveBrowserSession(
      createHumanUser(["KNOWLEDGE_ADMIN"]),
      createTrustedSession(["DATA_CURATOR"]),
    );

    expect(session.roles).toEqual(["DATA_CURATOR"]);
    expect(session.capabilities.has("intake:prepare")).toBe(true);
    expect(session.capabilities.has("admin:operate")).toBe(false);
  });

  it("rejects service identities even if a browser receives one", () => {
    expect(() =>
      resolveBrowserSession(createServiceUser(), createTrustedSession(["DATA_CURATOR"])),
    ).toThrow(BrowserIdentityError);
  });

  it("does not promote project-only KNOWLEDGE_ADMIN to organization admin", () => {
    const session = resolveBrowserSession(
      createHumanUser(["offline_access"]),
      createTrustedSession([], [
        {
          id: "00000000-0000-7000-8000-000000000012",
          roles: ["KNOWLEDGE_ADMIN"],
        },
      ]),
    );

    expect(session.organizationRoles).toEqual([]);
    expect(session.projects[0]?.roles).toEqual(["KNOWLEDGE_ADMIN"]);
    expect(session.capabilities.has("review:participate")).toBe(true);
    expect(session.capabilities.has("admin:operate")).toBe(false);
  });
});
