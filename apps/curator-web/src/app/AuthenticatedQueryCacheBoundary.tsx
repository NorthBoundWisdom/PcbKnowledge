import { useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useRef, type PropsWithChildren } from "react";

import type { BrowserSession } from "../auth/auth-types";
import { useAuthentication } from "../auth/use-authentication";

/**
 * Query keys isolate every DTO by trusted subject and organization. This boundary
 * additionally destroys the old identity's cache as soon as that trusted session
 * is revoked, replaced, or refreshed.
 */
export function AuthenticatedQueryCacheBoundary({ children }: PropsWithChildren) {
  const auth = useAuthentication();
  const queryClient = useQueryClient();
  const previousSession = useRef<BrowserSession | undefined>(auth.session);

  useLayoutEffect(() => {
    const prior = previousSession.current;
    if (prior !== undefined && prior !== auth.session) {
      queryClient.clear();
    }
    previousSession.current = auth.session;
  }, [auth.session, queryClient]);

  return children;
}
