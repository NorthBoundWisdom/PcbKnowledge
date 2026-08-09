import { Stack } from "@mui/material";
import { PageHeader } from "@pcbknowledge/ui-kit";

import {
  FailedRouteState,
  LoadingRouteState,
  type RouteFailureKind,
} from "../shared/RouteStatePanel";
import { DocumentIntakeForm } from "./DocumentIntakeForm";
import type {
  IntakeFormChoices,
  IntakeFormSubmission,
  UploadActivity,
} from "./intake-view-models";

export type IntakeOptionsViewState =
  | { readonly status: "loading" }
  | {
      readonly kind: RouteFailureKind;
      readonly onRetry?: () => void;
      readonly status: "failed";
    }
  | { readonly choices: IntakeFormChoices; readonly status: "ready" };

interface NewIntakePageViewProps {
  readonly activity: UploadActivity;
  readonly initialProjectId?: string;
  readonly onSubmit: (submission: IntakeFormSubmission) => void;
  readonly options: IntakeOptionsViewState;
}

export function NewIntakePageView({
  activity,
  initialProjectId,
  onSubmit,
  options,
}: NewIntakePageViewProps) {
  return (
    <Stack spacing={3}>
      <PageHeader
        badge="M2 intake"
        description="Upload one licensed PDF, bind its project scope and identity, then wait for server-side verification before it becomes available."
        eyebrow="Operate · Evidence Vault"
        title="New document intake"
      />
      {options.status === "loading" && (
        <LoadingRouteState label="Loading authorized project, source, scope, and license choices" />
      )}
      {options.status === "failed" && (
        <FailedRouteState kind={options.kind} onRetry={options.onRetry} />
      )}
      {options.status === "ready" && (
        <DocumentIntakeForm
          activity={activity}
          choices={options.choices}
          initialProjectId={initialProjectId}
          onSubmit={onSubmit}
        />
      )}
    </Stack>
  );
}
