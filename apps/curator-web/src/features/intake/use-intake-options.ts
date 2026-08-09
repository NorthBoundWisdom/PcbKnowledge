import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import type { components } from "../../api/generated";
import { useApiClientBoundary } from "../../api/client-boundary-context";
import { useAuthentication } from "../../auth/use-authentication";
import { useWorkspaceStore } from "../../state/workspace-store";
import { runGeneratedRequest, toRouteFailureKind } from "../shared/generated-request";
import { curatorQueryKeys } from "../shared/query-keys";
import type { IntakeOptionsViewState } from "./NewIntakePageView";
import type { IntakeFormChoices } from "./intake-view-models";

type IntakeOptionsResponse = components["schemas"]["IntakeOptionsResponse"];

function mapChoices(
  response: IntakeOptionsResponse,
  grantedProjectIds: ReadonlySet<string>,
): IntakeFormChoices {
  const projects = response.projects
    .filter((project) => grantedProjectIds.has(project.id))
    .map((project) => ({ id: project.id, label: project.display_name }));
  const visibleProjectIds = new Set(projects.map((project) => project.id));
  const accessScopes = response.access_scopes
    .filter((scope) => visibleProjectIds.has(scope.project_id))
    .map((scope) => ({ id: scope.id, label: scope.name, projectId: scope.project_id }));
  const visibleScopeIds = new Set(accessScopes.map((scope) => scope.id));
  return {
    accessScopes,
    licensePolicies: response.license_policies
      .filter((policy) => visibleScopeIds.has(policy.access_scope_id))
      .map((policy) => ({
        accessScopeId: policy.access_scope_id,
        allowsParsing: policy.allow_parse,
        allowsRawAccess: policy.allow_human_raw_access,
        id: policy.id,
        label: policy.name,
        secondary: policy.license_class,
      })),
    projects,
    sourceOrganizations: response.source_organizations.map((source) => ({
      id: source.id,
      label: source.name,
      secondary: source.authority_tier,
    })),
  };
}

function choicesAreUsable(choices: IntakeFormChoices): boolean {
  return (
    choices.projects.length > 0 &&
    choices.accessScopes.length > 0 &&
    choices.licensePolicies.length > 0 &&
    choices.sourceOrganizations.length > 0
  );
}

export function useIntakeOptions(): IntakeOptionsViewState {
  const api = useApiClientBoundary();
  const auth = useAuthentication();
  const rememberProjectLabels = useWorkspaceStore((state) => state.rememberProjectLabels);
  const grantedProjectIds = useMemo(
    () => new Set(auth.session?.projects.map((project) => project.id) ?? []),
    [auth.session],
  );
  const query = useQuery({
    enabled: auth.status === "authenticated",
    queryFn: () =>
      runGeneratedRequest(
        () => api.transport.GET("/intake/options"),
        auth.invalidateSession,
      ),
    queryKey: curatorQueryKeys.intakeOptions(auth.session),
    retry: false,
  });
  const choices = useMemo(
    () => (query.data === undefined ? undefined : mapChoices(query.data, grantedProjectIds)),
    [grantedProjectIds, query.data],
  );

  useEffect(() => {
    if (choices !== undefined) {
      rememberProjectLabels(choices.projects);
    }
  }, [choices, rememberProjectLabels]);

  if (query.isPending) return { status: "loading" };
  if (query.isError) {
    return { kind: toRouteFailureKind(query.error), onRetry: () => void query.refetch(), status: "failed" };
  }
  if (choices === undefined || !choicesAreUsable(choices)) {
    return { kind: "forbidden", status: "failed" };
  }
  return { choices, status: "ready" };
}
