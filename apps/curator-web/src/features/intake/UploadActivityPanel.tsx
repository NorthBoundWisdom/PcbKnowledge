import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import { Alert, LinearProgress, Stack, Typography } from "@mui/material";

import type { UploadActivity, UploadFailureKind } from "./intake-view-models";

const failureMessages: Readonly<Record<UploadFailureKind, string>> = {
  conflict: "This upload conflicts with an existing request. Review the document identity before retrying.",
  file_rejected: "The file was rejected. Select one valid PDF and review its size and format.",
  forbidden: "The selected project, source, scope, or license policy is not authorized.",
  network: "The staging upload was interrupted. The document was not assumed complete.",
  service_unavailable: "A required storage or verification service is temporarily unavailable.",
  unexpected: "The upload could not be completed. No document availability was inferred.",
  verification_failed: "Server-side PDF verification failed. The source was not added to the Evidence Vault.",
};

const phaseLabels = {
  available: "PDF verified and available",
  completing: "Queueing server-side verification…",
  reserving: "Reserving a private staging upload…",
  uploading: "Uploading PDF directly to private staging storage…",
  verifying: "Verifying bytes, hash, and PDF safety on the server…",
} as const;

interface UploadActivityPanelProps {
  readonly activity: Exclude<UploadActivity, { phase: "idle" }>;
}

export function UploadActivityPanel({ activity }: UploadActivityPanelProps) {
  if (activity.phase === "failed") {
    return (
      <Alert severity="error" variant="outlined">
        <Typography sx={{ fontWeight: 700 }} variant="body2">
          Upload failed
        </Typography>
        {failureMessages[activity.failure]}
      </Alert>
    );
  }
  if (activity.phase === "available") {
    return (
      <Alert icon={<CheckCircleOutlineRoundedIcon />} severity="success" variant="outlined">
        {phaseLabels.available}
      </Alert>
    );
  }

  const determinate = activity.phase === "uploading" && activity.percent !== undefined;
  return (
    <Stack aria-live="polite" spacing={1}>
      <Typography sx={{ fontWeight: 650 }} variant="body2">
        {phaseLabels[activity.phase]}
      </Typography>
      <LinearProgress
        aria-label="Document upload progress"
        value={determinate ? activity.percent : undefined}
        variant={determinate ? "determinate" : "indeterminate"}
      />
      {determinate && (
        <Typography color="text.secondary" variant="caption">
          {activity.percent}% uploaded
        </Typography>
      )}
    </Stack>
  );
}
