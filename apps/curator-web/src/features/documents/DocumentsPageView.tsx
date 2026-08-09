import AddRoundedIcon from "@mui/icons-material/AddRounded";
import {
  Button,
  Chip,
  Link as MuiLink,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import { PageHeader } from "@pcbknowledge/ui-kit";
import { Link } from "react-router-dom";

import {
  EmptyRouteState,
  FailedRouteState,
  LoadingRouteState,
  type RouteFailureKind,
} from "../shared/RouteStatePanel";
import type { DocumentListItemView } from "./document-view-models";

export type DocumentListViewState =
  | { readonly status: "loading" }
  | {
      readonly kind: RouteFailureKind;
      readonly onRetry?: () => void;
      readonly status: "failed";
    }
  | {
      readonly hasNextPage: boolean;
      readonly items: readonly DocumentListItemView[];
      readonly loadingNextPage: boolean;
      readonly onLoadNextPage: () => void;
      readonly status: "ready";
    };

interface DocumentsPageViewProps {
  readonly projectSelected: boolean;
  readonly state: DocumentListViewState;
}

export function DocumentsPageView({ projectSelected, state }: DocumentsPageViewProps) {
  return (
    <Stack spacing={3}>
      <PageHeader
        action={
          <Button component={Link} startIcon={<AddRoundedIcon />} to="/intake/new" variant="contained">
            Upload PDF
          </Button>
        }
        badge="M2 vault"
        description="Browse logical documents and the latest immutable revision visible in the selected project."
        eyebrow="Operate · Evidence Vault"
        title="Documents"
      />
      {!projectSelected && (
        <EmptyRouteState
          description="Choose a project in the workspace bar before loading document metadata."
          title="Select a project"
        />
      )}
      {projectSelected && state.status === "loading" && (
        <LoadingRouteState label="Loading project documents" />
      )}
      {projectSelected && state.status === "failed" && (
        <FailedRouteState kind={state.kind} onRetry={state.onRetry} />
      )}
      {projectSelected && state.status === "ready" && state.items.length === 0 && (
        <EmptyRouteState
          action={
            <Button component={Link} to="/intake/new" variant="contained">
              Upload the first PDF
            </Button>
          }
          description="No verified document revision is visible in this project."
          title="No documents"
        />
      )}
      {projectSelected && state.status === "ready" && state.items.length > 0 && (
        <Stack spacing={2}>
          <TableContainer>
            <Table aria-label="Documents" size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Document</TableCell>
                  <TableCell>Document no.</TableCell>
                  <TableCell>Revision</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {state.items.map((item) => (
                  <TableRow key={item.documentId} hover>
                    <TableCell>
                      <MuiLink component={Link} to={`/documents/${item.revisionId}`} underline="hover">
                        {item.title}
                      </MuiLink>
                    </TableCell>
                    <TableCell>{item.documentNumber ?? "—"}</TableCell>
                    <TableCell>{item.revisionLabel}</TableCell>
                    <TableCell>
                      <Chip label={item.state} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>{item.revisionCreatedAt}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {state.hasNextPage && (
            <Button
              disabled={state.loadingNextPage}
              onClick={state.onLoadNextPage}
              sx={{ alignSelf: "center" }}
              variant="outlined"
            >
              {state.loadingNextPage ? "Loading…" : "Load more"}
            </Button>
          )}
        </Stack>
      )}
    </Stack>
  );
}
