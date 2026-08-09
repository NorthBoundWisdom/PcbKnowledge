import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Divider,
  FormControl,
  FormControlLabel,
  FormHelperText,
  FormLabel,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { Controller, useForm, useWatch } from "react-hook-form";

import { ProjectSelector } from "../workspace/ProjectSelector";
import type {
  IntakeFormChoices,
  IntakeFormSubmission,
  UploadActivity,
} from "./intake-view-models";
import { UploadActivityPanel } from "./UploadActivityPanel";

interface IntakeFormFields {
  accessScopeId: string;
  confirmed: boolean;
  documentNumber: string;
  files: FileList;
  licensePolicyId: string;
  projectId: string;
  revisionLabel: string;
  sourceOrganizationId: string;
  title: string;
}

interface DocumentIntakeFormProps {
  readonly activity: UploadActivity;
  readonly choices: IntakeFormChoices;
  readonly initialProjectId?: string;
  readonly onSubmit: (submission: IntakeFormSubmission) => void;
}

function isValidPdf(files: FileList | undefined): true | string {
  if (files === undefined || files.length !== 1) {
    return "Select exactly one PDF file.";
  }
  const file = files.item(0);
  if (file === null || file.type !== "application/pdf" || !file.name.toLowerCase().endsWith(".pdf")) {
    return "Only a PDF file is accepted in this first release.";
  }
  return true;
}

export function DocumentIntakeForm({
  activity,
  choices,
  initialProjectId,
  onSubmit,
}: DocumentIntakeFormProps) {
  const defaultProjectId =
    (initialProjectId !== undefined &&
    choices.projects.some((project) => project.id === initialProjectId)
      ? initialProjectId
      : undefined) ??
    (choices.projects.length === 1 ? choices.projects[0]?.id : undefined) ??
    "";
  const {
    control,
    formState: { errors },
    handleSubmit,
    register,
    setValue,
  } = useForm<IntakeFormFields>({
    defaultValues: {
      accessScopeId: "",
      confirmed: false,
      documentNumber: "",
      licensePolicyId: "",
      projectId: defaultProjectId,
      revisionLabel: "",
      sourceOrganizationId: "",
      title: "",
    },
  });
  const selectedProjectId = useWatch({ control, name: "projectId" });
  const selectedScopeId = useWatch({ control, name: "accessScopeId" });
  const availableScopes = choices.accessScopes.filter(
    (scope) => scope.projectId === selectedProjectId,
  );
  const availablePolicies = choices.licensePolicies.filter(
    (policy) => policy.accessScopeId === selectedScopeId,
  );
  const busy = !["idle", "failed"].includes(activity.phase);

  const submit = handleSubmit((fields) => {
    const file = fields.files.item(0);
    if (file === null) {
      return;
    }
    const documentNumber = fields.documentNumber.trim();
    onSubmit({
      accessScopeId: fields.accessScopeId,
      documentNumber: documentNumber.length > 0 ? documentNumber : undefined,
      file,
      licensePolicyId: fields.licensePolicyId,
      projectId: fields.projectId,
      revisionLabel: fields.revisionLabel.trim(),
      sourceOrganizationId: fields.sourceOrganizationId,
      title: fields.title.trim(),
    });
  });

  return (
    <Card>
      <CardContent>
        <Box component="form" noValidate onSubmit={(event) => void submit(event)}>
          <Stack divider={<Divider flexItem />} spacing={3}>
            <Stack spacing={2}>
              <Box>
                <Typography component="h2" variant="h2">
                  1. Project and PDF
                </Typography>
                <Typography color="text.secondary" sx={{ mt: 0.5 }} variant="body2">
                  The project grant and immutable source bytes are bound before verification begins.
                </Typography>
              </Box>
              <Controller
                control={control}
                name="projectId"
                render={({ field }) => (
                  <ProjectSelector
                    disabled={busy}
                    label="Intake project"
                    onChange={(projectId) => {
                      field.onChange(projectId);
                      setValue("accessScopeId", "");
                      setValue("licensePolicyId", "");
                    }}
                    projects={choices.projects}
                    selectedProjectId={field.value || undefined}
                  />
                )}
                rules={{ required: "Select a project." }}
              />
              {errors.projectId !== undefined && (
                <FormHelperText error>{errors.projectId.message}</FormHelperText>
              )}
              <FormControl error={errors.files !== undefined}>
                <FormLabel htmlFor="intake-pdf">PDF file</FormLabel>
                <Box
                  accept="application/pdf,.pdf"
                  component="input"
                  id="intake-pdf"
                  sx={{ mt: 1 }}
                  type="file"
                  {...register("files", { validate: isValidPdf })}
                />
                <FormHelperText>
                  {errors.files?.message ?? "One PDF, uploaded directly to private staging storage."}
                </FormHelperText>
              </FormControl>
            </Stack>

            <Stack spacing={2}>
              <Box>
                <Typography component="h2" variant="h2">
                  2. Document identity
                </Typography>
                <Typography color="text.secondary" sx={{ mt: 0.5 }} variant="body2">
                  These fields create a logical document and its first immutable revision.
                </Typography>
              </Box>
              <TextField
                disabled={busy}
                error={errors.title !== undefined}
                fullWidth
                helperText={errors.title?.message}
                label="Title"
                {...register("title", {
                  required: "Enter a document title.",
                  validate: (value) => value.trim().length > 0 || "Enter a document title.",
                })}
              />
              <Stack direction="row" spacing={2}>
                <TextField
                  disabled={busy}
                  fullWidth
                  label="Document number (optional)"
                  {...register("documentNumber")}
                />
                <TextField
                  disabled={busy}
                  error={errors.revisionLabel !== undefined}
                  fullWidth
                  helperText={errors.revisionLabel?.message}
                  label="Revision"
                  {...register("revisionLabel", {
                    required: "Enter a revision label.",
                    validate: (value) => value.trim().length > 0 || "Enter a revision label.",
                  })}
                />
              </Stack>
            </Stack>

            <Stack spacing={2}>
              <Box>
                <Typography component="h2" variant="h2">
                  3. Source, scope, and license
                </Typography>
                <Typography color="text.secondary" sx={{ mt: 0.5 }} variant="body2">
                  Server policy remains authoritative for parsing and original-file access.
                </Typography>
              </Box>
              <Controller
                control={control}
                name="sourceOrganizationId"
                render={({ field }) => (
                  <TextField
                    {...field}
                    disabled={busy}
                    error={errors.sourceOrganizationId !== undefined}
                    fullWidth
                    helperText={errors.sourceOrganizationId?.message}
                    label="Source organization"
                    select
                  >
                    {choices.sourceOrganizations.map((source) => (
                      <MenuItem key={source.id} value={source.id}>
                        <ListItemText primary={source.label} secondary={source.secondary} />
                      </MenuItem>
                    ))}
                  </TextField>
                )}
                rules={{ required: "Select a source organization." }}
              />
              <Controller
                control={control}
                name="accessScopeId"
                render={({ field }) => (
                  <TextField
                    {...field}
                    disabled={busy || selectedProjectId.length === 0}
                    error={errors.accessScopeId !== undefined}
                    fullWidth
                    helperText={errors.accessScopeId?.message}
                    label="Access scope"
                    onChange={(event) => {
                      field.onChange(event);
                      setValue("licensePolicyId", "");
                    }}
                    select
                  >
                    {availableScopes.map((scope) => (
                      <MenuItem key={scope.id} value={scope.id}>
                        {scope.label}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
                rules={{ required: "Select an access scope." }}
              />
              <Controller
                control={control}
                name="licensePolicyId"
                render={({ field }) => (
                  <TextField
                    {...field}
                    disabled={busy || selectedScopeId.length === 0}
                    error={errors.licensePolicyId !== undefined}
                    fullWidth
                    helperText={errors.licensePolicyId?.message}
                    label="License policy"
                    select
                  >
                    {availablePolicies.map((policy) => (
                      <MenuItem key={policy.id} value={policy.id}>
                        <ListItemText
                          primary={policy.label}
                          secondary={`${policy.secondary ?? "Policy"} · parsing ${policy.allowsParsing ? "allowed" : "blocked"} · original ${policy.allowsRawAccess ? "allowed" : "blocked"}`}
                        />
                      </MenuItem>
                    ))}
                  </TextField>
                )}
                rules={{ required: "Select a license policy." }}
              />
              {availablePolicies.some((policy) => !policy.allowsParsing) && (
                <Alert severity="info" variant="outlined">
                  A policy may allow human retention while blocking parsing. The server applies the selected policy.
                </Alert>
              )}
            </Stack>

            <Stack spacing={2}>
              <Typography component="h2" variant="h2">
                4. Confirm and submit
              </Typography>
              <Controller
                control={control}
                name="confirmed"
                render={({ field }) => (
                  <FormControl error={errors.confirmed !== undefined}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={field.value}
                          disabled={busy}
                          onChange={(_, checked) => field.onChange(checked)}
                        />
                      }
                      label="I confirmed the source, project scope, license policy, and document identity."
                    />
                    <FormHelperText>{errors.confirmed?.message}</FormHelperText>
                  </FormControl>
                )}
                rules={{ validate: (value) => value || "Confirm the intake metadata before uploading." }}
              />
              {activity.phase !== "idle" && <UploadActivityPanel activity={activity} />}
              <Button
                disabled={busy}
                startIcon={<CloudUploadOutlinedIcon />}
                sx={{ alignSelf: "flex-start" }}
                type="submit"
                variant="contained"
              >
                {activity.phase === "failed" ? "Retry upload" : "Upload and verify PDF"}
              </Button>
            </Stack>
          </Stack>
        </Box>
      </CardContent>
    </Card>
  );
}
