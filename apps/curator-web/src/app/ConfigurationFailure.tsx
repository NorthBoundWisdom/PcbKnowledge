import ErrorOutlineIcon from "@mui/icons-material/ErrorOutlineOutlined";
import { Alert, AlertTitle, Box, Container, CssBaseline, List, ListItem, ThemeProvider } from "@mui/material";
import { curatorTheme } from "@pcbknowledge/ui-kit";

import type { RuntimeConfigurationError } from "../config/runtime-config";

interface ConfigurationFailureProps {
  error: RuntimeConfigurationError;
}

export function ConfigurationFailure({ error }: ConfigurationFailureProps) {
  return (
    <ThemeProvider theme={curatorTheme}>
      <CssBaseline />
      <Box sx={{ alignItems: "center", bgcolor: "background.default", display: "flex", minHeight: "100vh" }}>
        <Container maxWidth="sm">
          <Alert icon={<ErrorOutlineIcon />} severity="error" variant="outlined">
            <AlertTitle>Configuration required</AlertTitle>
            Curator Web stopped before startup because its public runtime configuration is incomplete.
            <List dense disablePadding sx={{ mt: 1 }}>
              {error.problems.map((problem) => (
                <ListItem disableGutters key={problem}>
                  {problem}
                </ListItem>
              ))}
            </List>
          </Alert>
        </Container>
      </Box>
    </ThemeProvider>
  );
}
