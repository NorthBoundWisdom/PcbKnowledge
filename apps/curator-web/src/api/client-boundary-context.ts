import { createContext, useContext } from "react";

import type { ApiClientBoundary } from "./client-boundary";

export const ApiClientBoundaryContext = createContext<ApiClientBoundary | null>(null);

export function useApiClientBoundary(): ApiClientBoundary {
  const boundary = useContext(ApiClientBoundaryContext);
  if (boundary === null) {
    throw new Error("useApiClientBoundary must be used inside AppProviders");
  }
  return boundary;
}
