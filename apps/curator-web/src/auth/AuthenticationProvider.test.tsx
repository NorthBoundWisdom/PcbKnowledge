import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { validRuntimeConfig } from "../test/test-config";
import {
  createHumanUser,
  createTrustedSession,
  FakeAuthClient,
} from "../test/fake-auth-client";
import { AuthenticationProvider } from "./AuthenticationProvider";
import { useAuthentication } from "./use-authentication";

function StatusProbe() {
  const auth = useAuthentication();
  return <output>{auth.status}</output>;
}

describe("AuthenticationProvider", () => {
  it("loads an approved in-memory user", async () => {
    const client = new FakeAuthClient(createHumanUser(["DOMAIN_REVIEWER"]));
    render(
      <AuthenticationProvider
        authClient={client}
        config={validRuntimeConfig}
        loadTrustedSession={() => Promise.resolve(createTrustedSession(["DOMAIN_REVIEWER"]))}
      >
        <StatusProbe />
      </AuthenticationProvider>,
    );

    expect(await screen.findByText("authenticated")).toBeVisible();
  });

  it("removes the user and expires the session when renewal fails", async () => {
    const client = new FakeAuthClient(createHumanUser(["DATA_CURATOR"]));
    render(
      <AuthenticationProvider
        authClient={client}
        config={validRuntimeConfig}
        loadTrustedSession={() => Promise.resolve(createTrustedSession(["DATA_CURATOR"]))}
      >
        <StatusProbe />
      </AuthenticationProvider>,
    );
    expect(await screen.findByText("authenticated")).toBeVisible();

    client.emitSilentRenewError();

    await waitFor(() => expect(screen.getByText("session_expired")).toBeVisible());
    expect(await client.getUser()).toBeNull();
  });

  it("fails closed and clears the token when trusted session bootstrap fails", async () => {
    const client = new FakeAuthClient(createHumanUser(["KNOWLEDGE_ADMIN"]));
    render(
      <AuthenticationProvider
        authClient={client}
        config={validRuntimeConfig}
        loadTrustedSession={() => Promise.reject(new Error("unavailable"))}
      >
        <StatusProbe />
      </AuthenticationProvider>,
    );

    expect(await screen.findByText("error")).toBeVisible();
    expect(await client.getUser()).toBeNull();
  });
});
