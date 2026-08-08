import {
  InMemoryWebStorage,
  UserManager,
  WebStorageStateStore,
  type UserManagerSettings,
} from "oidc-client-ts";

import type { RuntimeConfig } from "../config/runtime-config";
import type { AuthClient } from "./auth-types";

const transactionPrefix = "pcbknowledge.oidc.transaction.";
const inMemoryUserPrefix = "pcbknowledge.oidc.user.";

function applicationUrl(origin: string, path: string): string {
  return new URL(path, `${origin}/`).toString();
}

export function createOidcSettings(
  config: RuntimeConfig,
  origin: string,
  transactionStorage: Storage,
): UserManagerSettings {
  return {
    authority: config.oidc.issuerUrl,
    automaticSilentRenew: true,
    client_id: config.oidc.clientId,
    disablePKCE: false,
    filterProtocolClaims: true,
    includeIdTokenInSilentRenew: true,
    loadUserInfo: false,
    monitorSession: true,
    post_logout_redirect_uri: applicationUrl(origin, "/auth/logout/callback"),
    redirect_uri: applicationUrl(origin, "/auth/callback"),
    // Keep the one-time authorization code and state in the browser fragment;
    // fragments are never sent to Caddy or nginx access logs.
    response_mode: "fragment",
    response_type: "code",
    scope: "openid profile email roles",
    staleStateAgeInSeconds: 300,
    stateStore: new WebStorageStateStore({
      prefix: transactionPrefix,
      store: transactionStorage,
    }),
    userStore: new WebStorageStateStore({
      prefix: inMemoryUserPrefix,
      store: new InMemoryWebStorage(),
    }),
  };
}

export function createOidcClient(config: RuntimeConfig): AuthClient {
  const manager = new UserManager(
    createOidcSettings(config, window.location.origin, window.sessionStorage),
  );
  return {
    clearStaleState: () => manager.clearStaleState(),
    events: {
      addAccessTokenExpired: (callback) => manager.events.addAccessTokenExpired(callback),
      addSilentRenewError: (callback) => manager.events.addSilentRenewError(callback),
      addUserLoaded: (callback) => manager.events.addUserLoaded(callback),
      addUserSignedOut: (callback) => manager.events.addUserSignedOut(callback),
      addUserUnloaded: (callback) => manager.events.addUserUnloaded(callback),
    },
    getUser: () => manager.getUser(),
    removeUser: () => manager.removeUser(),
    signinRedirect: (arguments_) => manager.signinRedirect(arguments_),
    signinRedirectCallback: () => manager.signinRedirectCallback(),
    signoutRedirect: () => manager.signoutRedirect(),
    signoutRedirectCallback: () => manager.signoutRedirectCallback(),
  };
}

export const oidcTransactionStoragePrefix = transactionPrefix;
