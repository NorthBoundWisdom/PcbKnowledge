import { CssBaseline, ThemeProvider } from "@mui/material";
import { curatorTheme } from "@pcbknowledge/ui-kit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type PropsWithChildren } from "react";

import { ApiClientBoundaryContext } from "../api/client-boundary-context";
import { createApiClientBoundary, type ApiClientBoundary } from "../api/client-boundary";
import { AuthenticationProvider } from "../auth/AuthenticationProvider";
import type { AuthClient } from "../auth/auth-types";
import { createOidcClient } from "../auth/oidc-client";
import type { RuntimeConfig } from "../config/runtime-config";
import { AuthenticatedQueryCacheBoundary } from "./AuthenticatedQueryCacheBoundary";
import { RuntimeConfigContext } from "./runtime-config-context";

interface AppProvidersProps extends PropsWithChildren {
  authClient?: AuthClient;
  config: RuntimeConfig;
  loadTrustedSession?: ApiClientBoundary["loadTrustedSession"];
}

export function AppProviders({
  authClient,
  children,
  config,
  loadTrustedSession,
}: AppProvidersProps) {
  const [resolvedAuthClient] = useState<AuthClient>(() => authClient ?? createOidcClient(config));
  const [apiClientBoundary] = useState(() =>
    createApiClientBoundary(config, resolvedAuthClient),
  );
  const [sessionLoader] = useState(
    () => loadTrustedSession ?? apiClientBoundary.loadTrustedSession,
  );
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 30_000,
          },
        },
      }),
  );

  return (
    <RuntimeConfigContext.Provider value={config}>
      <AuthenticationProvider
        authClient={resolvedAuthClient}
        config={config}
        loadTrustedSession={sessionLoader}
      >
        <ApiClientBoundaryContext.Provider value={apiClientBoundary}>
          <QueryClientProvider client={queryClient}>
            <AuthenticatedQueryCacheBoundary>
              <ThemeProvider theme={curatorTheme}>
                <CssBaseline />
                {children}
              </ThemeProvider>
            </AuthenticatedQueryCacheBoundary>
          </QueryClientProvider>
        </ApiClientBoundaryContext.Provider>
      </AuthenticationProvider>
    </RuntimeConfigContext.Provider>
  );
}
