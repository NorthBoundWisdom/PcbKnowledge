import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Typography,
} from "@mui/material";
import { PageHeader } from "@pcbknowledge/ui-kit";

import {
  FailedRouteState,
  LoadingRouteState,
  type RouteFailureKind,
} from "../shared/RouteStatePanel";
import type { DocumentRevisionView, DownloadActivity } from "./document-view-models";

export type DocumentRevisionViewState =
  | { readonly status: "loading" }
  | {
      readonly kind: RouteFailureKind;
      readonly onRetry?: () => void;
      readonly status: "failed";
    }
  | { readonly revision: DocumentRevisionView; readonly status: "ready" };

interface DocumentRevisionPageViewProps {
  readonly download: DownloadActivity;
  readonly onDownload: () => void;
  readonly state: DocumentRevisionViewState;
}

function formatByteSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

export function DocumentRevisionPageView({
  download,
  onDownload,
  state,
}: DocumentRevisionPageViewProps) {
  return (
    <Stack spacing={3}>
      <PageHeader
        badge="M2 vault"
        description="Inspect immutable source metadata and request an audited, short-lived link to the authorized original PDF."
        eyebrow="Operate · Document revision"
        title={state.status === "ready" ? state.revision.title : "Document revision"}
      />
      {state.status === "loading" && <LoadingRouteState label="Loading document revision" />}
      {state.status === "failed" && (
        <FailedRouteState kind={state.kind} onRetry={state.onRetry} />
      )}
      {state.status === "ready" && (
        <Card>
          <CardContent>
            <Stack spacing={3}>
              <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                  <Chip color="success" label={state.revision.state} size="small" />
                  <Typography color="text.secondary" variant="body2">
                    Revision {state.revision.revisionLabel}
                  </Typography>
                </Stack>
                <Button
                  disabled={download.status === "authorizing"}
                  onClick={onDownload}
                  startIcon={
                    download.status === "authorizing" ? (
                      <CircularProgress color="inherit" size={16} />
                    ) : (
                      <DownloadRoundedIcon />
                    )
                  }
                  variant="contained"
                >
                  {download.status === "authorizing" ? "Authorizing…" : "Open authorized original"}
                </Button>
              </Stack>
              {download.status === "failed" && (
                <Alert severity="error" variant="outlined">
                  The audited original-file link could not be created. No anonymous or direct object path was used.
                </Alert>
              )}
              <Divider />
              <Stack divider={<Divider flexItem />}>
                {[
                  ["Project", state.revision.projectName],
                  ["Document number", state.revision.documentNumber ?? "—"],
                  ["Source organization", state.revision.sourceOrganizationName],
                  ["Original filename", state.revision.originalFilename],
                  ["Media type", state.revision.mediaType],
                  ["Size", formatByteSize(state.revision.byteSize)],
                  ["Created", state.revision.createdAt],
                ].map(([label, value]) => (
                  <Stack
                    direction="row"
                    key={label}
                    sx={{ alignItems: "center", justifyContent: "space-between", py: 1.25 }}
                  >
                    <Typography color="text.secondary" variant="body2">
                      {label}
                    </Typography>
                    <Typography sx={{ fontWeight: 600 }} variant="body2">
                      {value}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
              <Box>
                <Typography color="text.secondary" variant="caption">
                  SHA-256
                </Typography>
                <Typography
                  sx={{ fontFamily: "ui-monospace, SFMono-Regular, monospace", mt: 0.5, overflowWrap: "anywhere" }}
                  variant="body2"
                >
                  {state.revision.sha256}
                </Typography>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
}
