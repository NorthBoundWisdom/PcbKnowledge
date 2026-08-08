import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import type { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { AccessDeniedPage } from "../routes/auth/AccessDeniedPage";
import { SignInPage } from "../routes/auth/SignInPage";
import { useAuthentication } from "./use-authentication";

export function AuthenticationBoundary({ children }: PropsWithChildren) {
  const auth = useAuthentication();
  const location = useLocation();

  if (auth.status === "checking" || auth.status === "authenticating" || auth.status === "signing_out") {
    return (
      <Box sx={{ display: "grid", minHeight: "100vh", placeItems: "center" }}>
        <Stack spacing={2} sx={{ alignItems: "center" }}>
          <CircularProgress aria-label="Checking identity" size={32} />
          <Typography color="text.secondary" variant="body2">
            Verifying organization identity…
          </Typography>
        </Stack>
      </Box>
    );
  }

  if (auth.status === "error") {
    return <Navigate replace to={`/auth/error?reason=${auth.errorCode ?? "signin_failed"}`} />;
  }

  if (auth.status === "session_expired") {
    return <Navigate replace to="/auth/session-expired" />;
  }

  if (auth.status === "unauthenticated") {
    return <SignInPage returnUrl={`${location.pathname}${location.search}`} />;
  }

  if (!auth.can("workspace:access")) {
    return <AccessDeniedPage />;
  }

  return children;
}
