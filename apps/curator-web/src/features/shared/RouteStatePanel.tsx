import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import SearchOffRoundedIcon from "@mui/icons-material/SearchOffRounded";
import WifiOffRoundedIcon from "@mui/icons-material/WifiOffRounded";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";

export type RouteFailureKind =
  | "forbidden"
  | "not_found"
  | "service_unavailable"
  | "session_expired"
  | "unexpected";

interface LoadingRouteStateProps {
  readonly label: string;
}

export function LoadingRouteState({ label }: LoadingRouteStateProps) {
  return (
    <Card aria-live="polite">
      <CardContent>
        <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
          <CircularProgress aria-label={label} size={28} />
          <Box>
            <Typography component="h2" variant="h2">
              Loading
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.5 }} variant="body2">
              {label}
            </Typography>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

interface EmptyRouteStateProps {
  readonly action?: React.ReactNode;
  readonly description: string;
  readonly title: string;
}

export function EmptyRouteState({ action, description, title }: EmptyRouteStateProps) {
  return (
    <Card>
      <CardContent>
        <Stack spacing={2} sx={{ alignItems: "flex-start" }}>
          <SearchOffRoundedIcon color="disabled" />
          <Box>
            <Typography component="h2" variant="h2">
              {title}
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
              {description}
            </Typography>
          </Box>
          {action}
        </Stack>
      </CardContent>
    </Card>
  );
}

const failureContent: Readonly<
  Record<
    RouteFailureKind,
    {
      readonly description: string;
      readonly icon: typeof ErrorOutlineRoundedIcon;
      readonly title: string;
    }
  >
> = {
  forbidden: {
    description:
      "Your current project grant does not allow this operation. No protected data was loaded.",
    icon: LockOutlinedIcon,
    title: "Access denied",
  },
  not_found: {
    description:
      "The resource does not exist or is not visible in your current project. No additional details are available.",
    icon: SearchOffRoundedIcon,
    title: "Resource unavailable",
  },
  service_unavailable: {
    description: "A required service is temporarily unavailable. Your submitted data was not assumed complete.",
    icon: WifiOffRoundedIcon,
    title: "Service unavailable",
  },
  session_expired: {
    description: "The in-memory browser session has expired. Sign in again before loading workspace data.",
    icon: LockOutlinedIcon,
    title: "Session expired",
  },
  unexpected: {
    description: "The request could not be completed. No result was inferred from the failed response.",
    icon: ErrorOutlineRoundedIcon,
    title: "Request failed",
  },
};

interface FailedRouteStateProps {
  readonly kind: RouteFailureKind;
  readonly onRetry?: () => void;
}

export function FailedRouteState({ kind, onRetry }: FailedRouteStateProps) {
  const content = failureContent[kind];
  const Icon = content.icon;

  return (
    <Alert
      action={
        onRetry === undefined ? undefined : (
          <Button color="inherit" onClick={onRetry} size="small">
            Retry
          </Button>
        )
      }
      icon={<Icon fontSize="inherit" />}
      severity="error"
      variant="outlined"
    >
      <Typography component="h2" sx={{ fontWeight: 700 }} variant="body1">
        {content.title}
      </Typography>
      {content.description}
    </Alert>
  );
}
