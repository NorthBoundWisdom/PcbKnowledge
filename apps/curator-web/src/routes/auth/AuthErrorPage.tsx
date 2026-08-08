import { Alert, Button } from "@mui/material";
import { useSearchParams } from "react-router-dom";

import { useAuthentication } from "../../auth/use-authentication";
import type { AuthenticationErrorCode } from "../../auth/auth-types";
import { AuthSurface } from "./AuthSurface";

const safeReasons = new Set<AuthenticationErrorCode>([
  "callback_failed",
  "identity_not_allowed",
  "logout_failed",
  "session_bootstrap_failed",
  "session_renewal_failed",
  "signin_failed",
]);

export function AuthErrorPage() {
  const auth = useAuthentication();
  const [searchParams] = useSearchParams();
  const candidate = searchParams.get("reason") as AuthenticationErrorCode | null;
  const reason = candidate !== null && safeReasons.has(candidate) ? candidate : "signin_failed";
  const identityDenied = reason === "identity_not_allowed";

  return (
    <AuthSurface
      action={
        !identityDenied ? (
          <Button onClick={() => void auth.signIn("/dashboard")} variant="contained">
            Start a new sign-in
          </Button>
        ) : undefined
      }
      description="No token, provider payload, or sensitive error detail is displayed or logged."
      title={identityDenied ? "Identity not permitted" : "Authentication could not be completed"}
    >
      <Alert severity="error">
        {identityDenied
          ? "Curator Web requires an approved human role and rejects service-account identities."
          : "The authentication transaction failed closed. Start a new authorization transaction."}
      </Alert>
    </AuthSurface>
  );
}
