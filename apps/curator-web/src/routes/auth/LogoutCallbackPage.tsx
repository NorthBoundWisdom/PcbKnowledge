import { Alert, Button, CircularProgress } from "@mui/material";
import { useEffect, useState } from "react";

import { useAuthentication } from "../../auth/use-authentication";
import { AuthSurface } from "./AuthSurface";

type LogoutState = "working" | "complete" | "failed";

export function LogoutCallbackPage() {
  const auth = useAuthentication();
  const completeSignOut = auth.completeSignOut;
  const [state, setState] = useState<LogoutState>("working");

  useEffect(() => {
    let active = true;
    void completeSignOut()
      .then(() => {
        if (active) {
          setState("complete");
        }
      })
      .catch(() => {
        if (active) {
          setState("failed");
        }
      });
    return () => {
      active = false;
    };
  }, [completeSignOut]);

  return (
    <AuthSurface
      action={
        state === "complete" ? (
          <Button onClick={() => void auth.signIn("/dashboard")} variant="contained">
            Sign in again
          </Button>
        ) : undefined
      }
      description="Local in-memory credentials are cleared even when the identity provider cannot complete its response."
      title="Signing out"
    >
      {state === "working" && <CircularProgress aria-label="Completing sign-out" size={30} />}
      {state === "complete" && <Alert severity="success">You are signed out of Curator Web.</Alert>}
      {state === "failed" && (
        <Alert severity="error">The remote logout response could not be validated. Local credentials were cleared.</Alert>
      )}
    </AuthSurface>
  );
}
