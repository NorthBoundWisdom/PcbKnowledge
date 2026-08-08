import LogoutRoundedIcon from "@mui/icons-material/LogoutRounded";
import { Alert, Button } from "@mui/material";

import { useAuthentication } from "../../auth/use-authentication";
import { AuthSurface } from "./AuthSurface";

export function AccessDeniedPage() {
  const auth = useAuthentication();
  return (
    <AuthSurface
      action={
        <Button
          color="inherit"
          onClick={() => void auth.signOut()}
          startIcon={<LogoutRoundedIcon />}
          variant="outlined"
        >
          Sign out
        </Button>
      }
      description="Authentication alone does not grant access. The required human capability is absent."
      title="Access denied"
    >
      <Alert severity="error">
        Ask a knowledge administrator to review your organization role. No protected data was loaded.
      </Alert>
    </AuthSurface>
  );
}
