import type { BrowserSession } from "../../auth/auth-types";

type QueryIdentity = Pick<BrowserSession, "organizationId" | "subjectId"> | undefined;

function identityScope(identity: QueryIdentity) {
  return [identity?.subjectId ?? null, identity?.organizationId ?? null] as const;
}

export const curatorQueryKeys = {
  document(identity: QueryIdentity, revisionId: string | undefined) {
    return ["document-revision", ...identityScope(identity), revisionId ?? null] as const;
  },
  documents(identity: QueryIdentity, projectId: string | undefined) {
    return ["documents", ...identityScope(identity), projectId ?? null] as const;
  },
  intakeOptions(identity: QueryIdentity) {
    return ["intake-options", ...identityScope(identity)] as const;
  },
  uploadSession(identity: QueryIdentity, uploadSessionId: string) {
    return ["upload-session", ...identityScope(identity), uploadSessionId] as const;
  },
};
