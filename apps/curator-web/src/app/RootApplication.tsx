import type { ComponentProps } from "react";
import { RouterProvider } from "react-router-dom";

import {
  loadRuntimeConfig,
  RuntimeConfigurationError,
} from "../config/runtime-config";
import { AppProviders } from "./AppProviders";
import { ConfigurationFailure } from "./ConfigurationFailure";

interface RootApplicationProps {
  environment: Record<string, unknown>;
  router: ComponentProps<typeof RouterProvider>["router"];
}

type ConfigurationResolution =
  | { config: ReturnType<typeof loadRuntimeConfig>; error?: never }
  | { config?: never; error: RuntimeConfigurationError };

function resolveConfiguration(environment: Record<string, unknown>): ConfigurationResolution {
  try {
    return { config: loadRuntimeConfig(environment) };
  } catch (error) {
    if (error instanceof RuntimeConfigurationError) {
      return { error };
    }
    throw error;
  }
}

export function RootApplication({ environment, router }: RootApplicationProps) {
  const resolution = resolveConfiguration(environment);
  if (resolution.error !== undefined) {
    return <ConfigurationFailure error={resolution.error} />;
  }

  return (
    <AppProviders config={resolution.config}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
