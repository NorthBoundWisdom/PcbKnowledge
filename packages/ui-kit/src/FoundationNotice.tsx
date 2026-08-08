import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { Alert, AlertTitle, type AlertProps } from "@mui/material";

export interface FoundationNoticeProps extends Omit<AlertProps, "children" | "severity"> {
  detail?: string;
}

export function FoundationNotice({
  detail = "Navigation and platform boundaries are available; live domain workflows arrive in later milestones.",
  ...props
}: FoundationNoticeProps) {
  return (
    <Alert icon={<InfoOutlinedIcon fontSize="inherit" />} severity="info" variant="outlined" {...props}>
      <AlertTitle>M0 foundation only · No business data</AlertTitle>
      {detail}
    </Alert>
  );
}
