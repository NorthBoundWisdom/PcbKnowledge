import { Alert, Button } from "@mui/material";

import { useAuthentication } from "../../auth/use-authentication";
import { AuthSurface } from "./AuthSurface";

export function SessionExpiredPage() {
  const auth = useAuthentication();
  return (
    <AuthSurface
      action={
        <Button onClick={() => void auth.signIn("/dashboard")} variant="contained">
          Sign in again
        </Button>
      }
      description="The in-memory session was removed after expiry, provider sign-out, or failed renewal."
      title="Session expired"
    >
      <Alert severity="warning">No workspace data is available until a new sign-in succeeds.</Alert>
    </AuthSurface>
  );
}
