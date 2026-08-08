import { Box, Card, CardContent, Stack, Typography } from "@mui/material";
import type { PropsWithChildren, ReactNode } from "react";

interface AuthSurfaceProps extends PropsWithChildren {
  action?: ReactNode;
  description: string;
  title: string;
}

export function AuthSurface({ action, children, description, title }: AuthSurfaceProps) {
  return (
    <Box sx={{ display: "grid", minHeight: "100vh", p: 3, placeItems: "center" }}>
      <Card sx={{ maxWidth: 520, width: "100%" }}>
        <CardContent sx={{ p: 4 }}>
          <Stack spacing={2.5}>
            <Box
              aria-hidden="true"
              sx={{
                bgcolor: "text.primary",
                borderRadius: 1,
                color: "white",
                display: "grid",
                fontSize: 13,
                fontWeight: 800,
                height: 38,
                placeItems: "center",
                width: 38,
              }}
            >
              PK
            </Box>
            <Stack spacing={0.75}>
              <Typography component="h1" variant="h1">
                {title}
              </Typography>
              <Typography color="text.secondary" variant="body2">
                {description}
              </Typography>
            </Stack>
            {children}
            {action}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
