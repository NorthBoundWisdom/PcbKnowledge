import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import { Box, Card, CardContent, Chip, Divider, Stack, Typography } from "@mui/material";
import { FoundationNotice, PageHeader } from "@pcbknowledge/ui-kit";
import { useLocation } from "react-router-dom";

import type { FoundationRouteDefinition } from "./route-definitions";

interface FoundationPageProps {
  definition: FoundationRouteDefinition;
}

const boundaryItems = [
  ["Business records", "Intentionally absent"],
  ["API transport", "Generated client only"],
  ["Authorization", "Server-owned capability checks"],
] as const;

export function FoundationPage({ definition }: FoundationPageProps) {
  const location = useLocation();

  return (
    <Stack spacing={3}>
      <PageHeader
        description={definition.description}
        eyebrow={`${definition.group} · planned ${definition.milestone}`}
        title={definition.title}
      />
      <FoundationNotice />
      <Card>
        <CardContent>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center", justifyContent: "space-between" }}>
            <Box>
              <Typography component="h2" variant="h2">
                Route boundary is ready
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                The URL can be restored and linked now. Domain hooks are added only after generated contracts exist.
              </Typography>
            </Box>
            <Chip label={location.pathname} sx={{ fontFamily: "ui-monospace, SFMono-Regular, monospace" }} />
          </Stack>
          <Divider sx={{ my: 2.5 }} />
          <Stack divider={<Divider flexItem />}>
            {boundaryItems.map(([label, value]) => (
              <Stack
                direction="row"
                key={label}
                sx={{ alignItems: "center", justifyContent: "space-between", py: 1.25 }}
              >
                <Typography color="text.secondary" variant="body2">
                  {label}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                  <Typography sx={{ fontWeight: 650 }} variant="body2">
                    {value}
                  </Typography>
                  <ArrowForwardRoundedIcon color="disabled" fontSize="small" />
                </Stack>
              </Stack>
            ))}
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
