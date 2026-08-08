import { useContext } from "react";

import { AuthenticationContext } from "./auth-context";

export function useAuthentication() {
  const context = useContext(AuthenticationContext);
  if (context === null) {
    throw new Error("useAuthentication must be used inside AuthenticationProvider");
  }
  return context;
}
