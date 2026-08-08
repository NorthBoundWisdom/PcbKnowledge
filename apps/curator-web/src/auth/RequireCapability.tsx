import type { PropsWithChildren } from "react";

import { AccessDeniedPage } from "../routes/auth/AccessDeniedPage";
import type { BrowserCapability } from "./auth-types";
import { useAuthentication } from "./use-authentication";

interface RequireCapabilityProps extends PropsWithChildren {
  capability: BrowserCapability;
}

export function RequireCapability({ capability, children }: RequireCapabilityProps) {
  const auth = useAuthentication();
  return auth.can(capability) ? children : <AccessDeniedPage />;
}
