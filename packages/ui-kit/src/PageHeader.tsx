import { Box, Chip, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

export interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
  badge?: string;
}

export function PageHeader({
  action,
  badge = "Foundation",
  description,
  eyebrow,
  title,
}: PageHeaderProps) {
  return (
    <Stack direction="row" spacing={3} sx={{ alignItems: "flex-start", justifyContent: "space-between" }}>
      <Box sx={{ minWidth: 0 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography color="primary.dark" variant="overline">
            {eyebrow}
          </Typography>
          <Chip color="default" label={badge} size="small" variant="outlined" />
        </Stack>
        <Typography component="h1" sx={{ mt: 0.5 }} variant="h1">
          {title}
        </Typography>
        <Typography color="text.secondary" sx={{ maxWidth: 760, mt: 1 }} variant="body2">
          {description}
        </Typography>
      </Box>
      {action}
    </Stack>
  );
}
