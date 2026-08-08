import { CssBaseline, ThemeProvider } from "@mui/material";
import { curatorTheme } from "@pcbknowledge/ui-kit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type PropsWithChildren } from "react";

import type { RuntimeConfig } from "../config/runtime-config";
import { RuntimeConfigContext } from "./runtime-config-context";

interface AppProvidersProps extends PropsWithChildren {
  config: RuntimeConfig;
}

export function AppProviders({ children, config }: AppProvidersProps) {
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
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={curatorTheme}>
          <CssBaseline />
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    </RuntimeConfigContext.Provider>
  );
}
