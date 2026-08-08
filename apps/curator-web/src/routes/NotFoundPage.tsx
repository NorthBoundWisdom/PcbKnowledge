import { Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <Card sx={{ maxWidth: 640 }}>
      <CardContent>
        <Stack spacing={2} sx={{ alignItems: "flex-start" }}>
          <Typography color="primary.dark" variant="overline">
            Route not found
          </Typography>
          <Typography component="h1" variant="h1">
            This workspace route does not exist
          </Typography>
          <Typography color="text.secondary">
            No fallback data was loaded. Return to the foundation dashboard to choose a defined work area.
          </Typography>
          <Button component={Link} to="/dashboard" variant="contained">
            Return to dashboard
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
