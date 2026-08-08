import type { User } from "oidc-client-ts";
import { z } from "zod";

import type { components } from "../api/generated";

export const humanRoles = [
  "DATA_CURATOR",
  "DOMAIN_REVIEWER",
  "KNOWLEDGE_ADMIN",
  "AUDITOR",
] as const;

export const agentServiceRole = "AGENT_SERVICE" as const;

export type HumanRole = (typeof humanRoles)[number];

export type BrowserCapability =
  | "workspace:access"
  | "evidence:read"
  | "intake:prepare"
  | "review:participate"
  | "evaluation:read"
  | "audit:read"
  | "admin:operate";

const roleCapabilities: Readonly<Record<HumanRole, readonly BrowserCapability[]>> = {
  DATA_CURATOR: ["workspace:access", "evidence:read", "intake:prepare", "review:participate"],
  DOMAIN_REVIEWER: [
    "workspace:access",
    "evidence:read",
    "review:participate",
    "evaluation:read",
  ],
  KNOWLEDGE_ADMIN: [
    "workspace:access",
    "evidence:read",
    "intake:prepare",
    "review:participate",
    "evaluation:read",
    "audit:read",
    "admin:operate",
  ],
  AUDITOR: ["workspace:access", "evidence:read", "evaluation:read", "audit:read"],
};

const identityProfileSchema = z.object({
  sub: z.string().min(1),
  name: z.string().min(1).optional(),
  preferred_username: z.string().min(1).optional(),
  email: z.string().email().optional(),
  pcbknowledge_subject_kind: z.literal("HUMAN"),
  realm_access: z.object({ roles: z.array(z.string()) }).optional(),
});

export type TrustedSessionProjection = components["schemas"]["SessionResponse"];

const humanRoleSchema = z.enum(humanRoles);
const trustedSessionProjectionSchema = z.object({
  authenticated_at: z.iso.datetime({ offset: true }),
  organization_id: z.uuid(),
  organization_roles: z.array(humanRoleSchema),
  projects: z.array(
    z.object({
      id: z.uuid(),
      roles: z.array(humanRoleSchema).min(1),
    }),
  ),
  subject_id: z.uuid(),
  subject_kind: z.literal("HUMAN"),
});

export interface BrowserIdentity {
  readonly displayName: string;
  readonly subject: string;
}

export interface BrowserProjectGrant {
  readonly id: string;
  readonly roles: readonly HumanRole[];
}

export interface BrowserSession {
  readonly capabilities: ReadonlySet<BrowserCapability>;
  readonly displayName: string;
  readonly organizationId: string;
  readonly organizationRoles: readonly HumanRole[];
  readonly projects: readonly BrowserProjectGrant[];
  readonly roles: readonly HumanRole[];
  readonly subjectId: string;
}

export type AuthenticationStatus =
  | "checking"
  | "authenticating"
  | "authenticated"
  | "unauthenticated"
  | "session_expired"
  | "signing_out"
  | "error";

export type AuthenticationErrorCode =
  | "callback_failed"
  | "identity_not_allowed"
  | "logout_failed"
  | "session_bootstrap_failed"
  | "session_renewal_failed"
  | "signin_failed";

export interface AuthClientEvents {
  addAccessTokenExpired(callback: () => void): () => void;
  addSilentRenewError(callback: () => void): () => void;
  addUserLoaded(callback: (user: User) => void): () => void;
  addUserSignedOut(callback: () => void): () => void;
  addUserUnloaded(callback: () => void): () => void;
}

export interface AuthClient {
  readonly events: AuthClientEvents;
  clearStaleState(): Promise<void>;
  getUser(): Promise<User | null>;
  removeUser(): Promise<void>;
  signinRedirect(arguments_: { state: unknown }): Promise<void>;
  signinRedirectCallback(): Promise<User>;
  signoutRedirect(): Promise<void>;
  signoutRedirectCallback(): Promise<unknown>;
}

export class BrowserIdentityError extends Error {
  constructor() {
    super("The identity is not allowed to use Curator Web");
    this.name = "BrowserIdentityError";
  }
}

export function resolveBrowserIdentity(user: User): BrowserIdentity {
  if (user.expired) {
    throw new BrowserIdentityError();
  }

  const parsed = identityProfileSchema.safeParse(user.profile);
  if (!parsed.success || parsed.data.realm_access?.roles.includes(agentServiceRole)) {
    throw new BrowserIdentityError();
  }

  return Object.freeze({
    displayName:
      parsed.data.name ??
      parsed.data.preferred_username ??
      parsed.data.email ??
      parsed.data.sub,
    subject: parsed.data.sub,
  });
}

export function resolveBrowserSession(
  user: User,
  projection: TrustedSessionProjection,
): BrowserSession {
  const identity = resolveBrowserIdentity(user);
  const parsed = trustedSessionProjectionSchema.safeParse(projection);
  if (!parsed.success) {
    throw new BrowserIdentityError();
  }

  const projects = parsed.data.projects.map((project) =>
    Object.freeze({ id: project.id, roles: Object.freeze(project.roles) }),
  );
  const roles = [
    ...new Set([
      ...parsed.data.organization_roles,
      ...projects.flatMap((project) => project.roles),
    ]),
  ];
  if (roles.length === 0) {
    throw new BrowserIdentityError();
  }

  const capabilities = new Set<BrowserCapability>();
  for (const role of parsed.data.organization_roles) {
    for (const capability of roleCapabilities[role]) {
      capabilities.add(capability);
    }
  }
  for (const project of projects) {
    for (const role of project.roles) {
      for (const capability of roleCapabilities[role]) {
        if (capability !== "admin:operate") {
          capabilities.add(capability);
        }
      }
    }
  }

  return Object.freeze({
    capabilities,
    displayName: identity.displayName,
    organizationId: parsed.data.organization_id,
    organizationRoles: Object.freeze(parsed.data.organization_roles),
    projects: Object.freeze(projects),
    roles: Object.freeze(roles),
    subjectId: parsed.data.subject_id,
  });
}

export function hasCapability(
  session: BrowserSession,
  capability: BrowserCapability,
): boolean {
  return session.capabilities.has(capability);
}
