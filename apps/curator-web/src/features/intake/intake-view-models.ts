import type { ProjectSelectorOption } from "../workspace/ProjectSelector";
export type { RecentUploadSummary as IntakeStatusItem } from "../../state/workspace-store";

/** Presentation-only choices; generated API responses are mapped into these in feature hooks. */
export interface IntakeChoice {
  readonly id: string;
  readonly label: string;
  readonly secondary?: string;
}

export interface IntakeScopeChoice extends IntakeChoice {
  readonly projectId: string;
}

export interface IntakeLicenseChoice extends IntakeChoice {
  readonly accessScopeId: string;
  readonly allowsParsing: boolean;
  readonly allowsRawAccess: boolean;
}

export interface IntakeFormChoices {
  readonly accessScopes: readonly IntakeScopeChoice[];
  readonly licensePolicies: readonly IntakeLicenseChoice[];
  readonly projects: readonly ProjectSelectorOption[];
  readonly sourceOrganizations: readonly IntakeChoice[];
}

/** Browser form state, deliberately distinct from the generated HTTP request type. */
export interface IntakeFormSubmission {
  readonly accessScopeId: string;
  readonly documentNumber?: string;
  readonly file: File;
  readonly licensePolicyId: string;
  readonly projectId: string;
  readonly revisionLabel: string;
  readonly sourceOrganizationId: string;
  readonly title: string;
}

export type UploadFailureKind =
  | "conflict"
  | "file_rejected"
  | "forbidden"
  | "network"
  | "service_unavailable"
  | "unexpected"
  | "verification_failed";

export type UploadActivity =
  | { readonly phase: "idle" }
  | { readonly phase: "reserving" }
  | { readonly percent?: number; readonly phase: "uploading" }
  | { readonly phase: "completing" }
  | { readonly phase: "verifying" }
  | { readonly phase: "available" }
  | { readonly failure: UploadFailureKind; readonly phase: "failed" };
