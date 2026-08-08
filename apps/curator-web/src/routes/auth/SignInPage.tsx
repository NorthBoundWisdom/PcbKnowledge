import LoginRoundedIcon from "@mui/icons-material/LoginRounded";
import { Alert, Button } from "@mui/material";

import { useAuthentication } from "../../auth/use-authentication";
import { AuthSurface } from "./AuthSurface";

export function SignInPage({ returnUrl = "/dashboard" }: { returnUrl?: string }) {
  const auth = useAuthentication();

  return (
    <AuthSurface
      action={
        <Button
          onClick={() => void auth.signIn(returnUrl)}
          startIcon={<LoginRoundedIcon />}
          variant="contained"
        >
          Sign in with organization identity
        </Button>
      }
      description="Curator Web uses Authorization Code with PKCE. No access or refresh token is written to browser persistent storage."
      title="Sign in to PcbKnowledge"
    >
      <Alert severity="info">
        A trusted active human membership is required. Service accounts and identities without a database-backed Curator Web capability are denied.
      </Alert>
    </AuthSurface>
  );
}
