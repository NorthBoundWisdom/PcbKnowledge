import AddRoundedIcon from "@mui/icons-material/AddRounded";
import {
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { PageHeader } from "@pcbknowledge/ui-kit";
import { Link } from "react-router-dom";

import { EmptyRouteState } from "../shared/RouteStatePanel";
import type { IntakeStatusItem } from "./intake-view-models";

interface IntakeInboxPageViewProps {
  readonly items: readonly IntakeStatusItem[];
}

function statusColor(state: string): "default" | "error" | "info" | "success" | "warning" {
  if (state === "FAILED") return "error";
  if (state === "STORED") return "success";
  if (state === "RETRYING") return "warning";
  if (state === "QUEUED" || state === "VERIFYING") return "info";
  return "default";
}

export function IntakeInboxPageView({ items }: IntakeInboxPageViewProps) {
  return (
    <Stack spacing={3}>
      <PageHeader
        action={
          <Button component={Link} startIcon={<AddRoundedIcon />} to="/intake/new" variant="contained">
            Upload PDF
          </Button>
        }
        badge="M2 intake"
        description="Track PDFs submitted from this browser workspace while server-side verification is in progress."
        eyebrow="Operate · Intake"
        title="Intake inbox"
      />
      {items.length === 0 ? (
        <EmptyRouteState
          action={
            <Button component={Link} to="/intake/new" variant="contained">
              Upload the first PDF
            </Button>
          }
          description="No recent upload is being tracked in this browser workspace."
          title="No recent intake"
        />
      ) : (
        <Card>
          <CardContent>
            <List disablePadding>
              {items.map((item, index) => (
                <Stack key={item.id}>
                  {index > 0 && <Divider />}
                  <ListItem
                    secondaryAction={
                      <Chip color={statusColor(item.state)} label={item.state} size="small" />
                    }
                    sx={{ px: 0, py: 1.5 }}
                  >
                    <ListItemText
                      primary={item.title}
                      secondary={
                        <>
                          <Typography component="span" variant="caption">
                            Updated {item.updatedAt}
                          </Typography>
                          {item.failureCode !== undefined && (
                            <Typography color="error" component="span" sx={{ ml: 1 }} variant="caption">
                              Verification did not complete; review the bounded failure category.
                            </Typography>
                          )}
                        </>
                      }
                    />
                  </ListItem>
                </Stack>
              ))}
            </List>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
}
