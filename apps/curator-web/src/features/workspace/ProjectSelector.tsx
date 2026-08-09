import { FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { useId } from "react";

export interface ProjectSelectorOption {
  readonly id: string;
  readonly label: string;
}

interface ProjectSelectorProps {
  readonly disabled?: boolean;
  readonly label?: string;
  readonly onChange: (projectId: string) => void;
  readonly projects: readonly ProjectSelectorOption[];
  readonly selectedProjectId?: string;
}

export function ProjectSelector({
  disabled: disabledByCaller = false,
  label = "Project",
  onChange,
  projects,
  selectedProjectId,
}: ProjectSelectorProps) {
  const labelId = useId();
  const noProjects = projects.length === 0;
  const disabled = disabledByCaller || noProjects;

  return (
    <FormControl disabled={disabled} size="small" sx={{ minWidth: 240 }}>
      <InputLabel id={labelId} shrink>
        {label}
      </InputLabel>
      <Select
        aria-label={label}
        displayEmpty
        label={label}
        labelId={labelId}
        onChange={(event) => onChange(event.target.value)}
        renderValue={(value) =>
          value.length === 0
            ? noProjects
              ? "No project access"
              : "Select a project"
            : projects.find((project) => project.id === value)?.label
        }
        value={selectedProjectId ?? ""}
      >
        <MenuItem disabled value="">
          {noProjects ? "No project access" : "Select a project"}
        </MenuItem>
        {projects.map((project) => (
          <MenuItem key={project.id} value={project.id}>
            {project.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
