import { Alert, CircularProgress } from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthentication } from "../../auth/use-authentication";
import { AuthSurface } from "./AuthSurface";

export function AuthCallbackPage() {
  const { completeSignIn } = useAuthentication();
  const navigate = useNavigate();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    void completeSignIn()
      .then((returnUrl) => {
        if (active) {
          navigate(returnUrl, { replace: true });
        }
      })
      .catch(() => {
        if (active) {
          setFailed(true);
        }
      });
    return () => {
      active = false;
    };
  }, [completeSignIn, navigate]);

  return (
    <AuthSurface
      description="The authorization response is being validated against the issuer, client, state, nonce, and PKCE transaction."
      title="Completing sign-in"
    >
      {failed ? (
        <Alert severity="error">The authorization response was rejected. Start a new sign-in from this browser.</Alert>
      ) : (
        <CircularProgress aria-label="Completing sign-in" size={30} />
      )}
    </AuthSurface>
  );
}
