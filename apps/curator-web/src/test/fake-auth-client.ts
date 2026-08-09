import { User } from "oidc-client-ts";

import type {
  AuthClient,
  HumanRole,
  TrustedSessionProjection,
} from "../auth/auth-types";

type Unsubscribe = () => void;

class CallbackSet<T extends (...arguments_: never[]) => void> {
  private readonly callbacks = new Set<T>();

  add(callback: T): Unsubscribe {
    this.callbacks.add(callback);
    return () => this.callbacks.delete(callback);
  }

  emit(...arguments_: Parameters<T>): void {
    for (const callback of this.callbacks) {
      callback(...arguments_);
    }
  }
}

export class FakeAuthClient implements AuthClient {
  private readonly accessTokenExpired = new CallbackSet<() => void>();
  private readonly silentRenewError = new CallbackSet<() => void>();
  private readonly userLoaded = new CallbackSet<(user: User) => void>();
  private readonly userSignedOut = new CallbackSet<() => void>();
  private readonly userUnloaded = new CallbackSet<() => void>();
  private currentUser: User | null;

  callbackUser: User;
  lastSignInState: unknown;
  signInFailure = false;
  signOutFailure = false;

  readonly events = {
    addAccessTokenExpired: (callback: () => void) => this.accessTokenExpired.add(callback),
    addSilentRenewError: (callback: () => void) => this.silentRenewError.add(callback),
    addUserLoaded: (callback: (user: User) => void) => this.userLoaded.add(callback),
    addUserSignedOut: (callback: () => void) => this.userSignedOut.add(callback),
    addUserUnloaded: (callback: () => void) => this.userUnloaded.add(callback),
  };

  constructor(user: User | null = null) {
    this.currentUser = user;
    this.callbackUser = user ?? createHumanUser(["DATA_CURATOR"]);
  }

  async clearStaleState(): Promise<void> {}

  async getUser(): Promise<User | null> {
    return this.currentUser;
  }

  async removeUser(): Promise<void> {
    this.currentUser = null;
    this.userUnloaded.emit();
  }

  async signinRedirect(arguments_: { state: unknown }): Promise<void> {
    this.lastSignInState = arguments_.state;
    if (this.signInFailure) {
      throw new Error("synthetic sign-in failure");
    }
  }

  async signinRedirectCallback(): Promise<User> {
    if (this.signInFailure) {
      throw new Error("synthetic callback failure");
    }
    this.currentUser = this.callbackUser;
    this.userLoaded.emit(this.callbackUser);
    return this.callbackUser;
  }

  async signoutRedirect(): Promise<void> {
    if (this.signOutFailure) {
      throw new Error("synthetic sign-out failure");
    }
  }

  async signoutRedirectCallback(): Promise<void> {
    if (this.signOutFailure) {
      throw new Error("synthetic logout callback failure");
    }
    await this.removeUser();
  }

  emitAccessTokenExpired(): void {
    this.accessTokenExpired.emit();
  }

  emitSilentRenewError(): void {
    this.silentRenewError.emit();
  }

  emitUserLoaded(user: User): void {
    this.currentUser = user;
    this.userLoaded.emit(user);
  }

  emitUserSignedOut(): void {
    this.userSignedOut.emit();
  }
}

export function createHumanUser(
  roles: string[],
  userState?: unknown,
  subject = "00000000-0000-7000-8000-000000000001",
): User {
  const issuedAt = Math.floor(Date.now() / 1000);
  return new User({
    access_token: "synthetic-access-token-held-only-by-the-test-object",
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    profile: {
      aud: "pcbknowledge-curator-web",
      exp: issuedAt + 3600,
      iat: issuedAt,
      iss: "https://identity.example.test/realms/pcbknowledge",
      name: "Mina Curator",
      pcbknowledge_subject_kind: "HUMAN",
      preferred_username: "mina",
      realm_access: { roles },
      sub: subject,
    },
    refresh_token: "synthetic-refresh-token-held-only-by-the-test-object",
    token_type: "Bearer",
    userState,
  });
}

export function createServiceUser(): User {
  const issuedAt = Math.floor(Date.now() / 1000);
  return new User({
    access_token: "synthetic-service-token-held-only-by-the-test-object",
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    profile: {
      aud: "pcbknowledge-api",
      exp: issuedAt + 3600,
      iat: issuedAt,
      iss: "https://identity.example.test/realms/pcbknowledge",
      pcbknowledge_subject_kind: "SERVICE_ACCOUNT",
      preferred_username: "service-account-pcbknowledge-agent-service",
      realm_access: { roles: ["AGENT_SERVICE"] },
      sub: "00000000-0000-7000-8000-000000000002",
    },
    token_type: "Bearer",
  });
}

export function createTrustedSession(
  organizationRoles: HumanRole[],
  projects: TrustedSessionProjection["projects"] = [],
): TrustedSessionProjection {
  return {
    authenticated_at: new Date().toISOString(),
    organization_id: "00000000-0000-7000-8000-000000000010",
    organization_roles: organizationRoles,
    projects,
    subject_id: "00000000-0000-7000-8000-000000000011",
    subject_kind: "HUMAN",
  };
}
