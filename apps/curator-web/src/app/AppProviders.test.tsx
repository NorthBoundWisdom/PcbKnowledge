import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it } from "vitest";

import { useAuthentication } from "../auth/use-authentication";
import { curatorQueryKeys } from "../features/shared/query-keys";
import {
  createHumanUser,
  createTrustedSession,
  FakeAuthClient,
} from "../test/fake-auth-client";
import { validRuntimeConfig } from "../test/test-config";
import { AppProviders } from "./AppProviders";

const projectId = "00000000-0000-7000-8000-000000000021";
const subjectA = "00000000-0000-7000-8000-000000000011";
const subjectB = "00000000-0000-7000-8000-000000000012";

function ScopedDocumentProbe({ expose }: { expose: (client: QueryClient) => void }) {
  const auth = useAuthentication();
  const queryClient = useQueryClient();
  const query = useQuery<{ title: string }>({
    enabled: false,
    queryFn: () => Promise.reject(new Error("disabled cache probe must not load")),
    queryKey: curatorQueryKeys.documents(auth.session, projectId),
  });

  useEffect(() => expose(queryClient), [expose, queryClient]);

  return (
    <>
      <output aria-label="Authentication status">{auth.status}</output>
      <output aria-label="Trusted subject">{auth.session?.subjectId ?? "none"}</output>
      <output aria-label="Visible cached document">{query.data?.title ?? "none"}</output>
      <button onClick={() => void auth.invalidateSession()} type="button">
        Invalidate session
      </button>
    </>
  );
}

describe("AppProviders identity-scoped query cache", () => {
  it("destroys A's DTOs before B can enter the same organization and project", async () => {
    const userA = createHumanUser(["DATA_CURATOR"], undefined, "oidc-subject-a");
    const userB = createHumanUser(["DATA_CURATOR"], undefined, "oidc-subject-b");
    const authClient = new FakeAuthClient(userA);
    const sessionA = {
      ...createTrustedSession([], [{ id: projectId, roles: ["DATA_CURATOR"] }]),
      subject_id: subjectA,
    };
    const sessionB = {
      ...createTrustedSession([], [{ id: projectId, roles: ["DATA_CURATOR"] }]),
      subject_id: subjectB,
    };
    let trustedSession = sessionA;
    let cache: QueryClient | undefined;
    const expose = (client: QueryClient) => {
      cache = client;
    };

    render(
      <AppProviders
        authClient={authClient}
        config={validRuntimeConfig}
        loadTrustedSession={() => Promise.resolve(trustedSession)}
      >
        <ScopedDocumentProbe expose={expose} />
      </AppProviders>,
    );

    expect(await screen.findByText(subjectA)).toBeVisible();
    const aKey = curatorQueryKeys.documents(
      { organizationId: sessionA.organization_id, subjectId: subjectA },
      projectId,
    );
    act(() => cache?.setQueryData(aKey, { title: "A-only document" }));
    expect(await screen.findByText("A-only document")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Invalidate session" }));
    await waitFor(() => expect(screen.getByLabelText("Authentication status")).toHaveTextContent("session_expired"));
    expect(cache?.getQueryData(aKey)).toBeUndefined();

    trustedSession = sessionB;
    act(() => authClient.emitUserLoaded(userB));

    expect(await screen.findByText(subjectB)).toBeVisible();
    expect(screen.getByLabelText("Visible cached document")).toHaveTextContent("none");
    expect(cache?.getQueryData(aKey)).toBeUndefined();
  });
});
