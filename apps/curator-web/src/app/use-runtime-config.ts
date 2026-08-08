import { useContext } from "react";

import { RuntimeConfigContext } from "./runtime-config-context";

export function useRuntimeConfig() {
  const config = useContext(RuntimeConfigContext);
  if (config === null) {
    throw new Error("useRuntimeConfig must be used inside AppProviders");
  }
  return config;
}
