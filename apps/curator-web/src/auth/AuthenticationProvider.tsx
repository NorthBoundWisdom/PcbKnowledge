import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from "react";
import type { User } from "oidc-client-ts";

import type { RuntimeConfig } from "../config/runtime-config";
import { AuthenticationContext, type AuthenticationContextValue } from "./auth-context";
import {
  BrowserIdentityError,
  hasCapability,
  resolveBrowserIdentity,
  resolveBrowserSession,
  type AuthClient,
  type AuthenticationErrorCode,
  type AuthenticationStatus,
  type BrowserSession,
  type TrustedSessionProjection,
} from "./auth-types";
import { createOidcClient } from "./oidc-client";

interface AuthenticationProviderProps extends PropsWithChildren {
  authClient?: AuthClient;
  config: RuntimeConfig;
  loadTrustedSession: () => Promise<TrustedSessionProjection>;
}

interface AuthenticationState {
  errorCode?: AuthenticationErrorCode;
  session?: BrowserSession;
  status: AuthenticationStatus;
}

interface SignInState {
  returnUrl?: unknown;
}

function safeReturnUrl(value: unknown): string {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return "/dashboard";
  }
  if (value.startsWith("/auth/")) {
    return "/dashboard";
  }
  return value;
}

function errorState(errorCode: AuthenticationErrorCode): AuthenticationState {
  return { errorCode, status: "error" };
}

export function AuthenticationProvider({
  authClient,
  children,
  config,
  loadTrustedSession,
}: AuthenticationProviderProps) {
  const [client] = useState<AuthClient>(() => authClient ?? createOidcClient(config));
  const [state, setState] = useState<AuthenticationState>({ status: "checking" });
  const bootstrapRef = useRef<Promise<BrowserSession | null> | null>(null);

  const acceptUser = useCallback(
    (user: User): Promise<BrowserSession | null> => {
      if (bootstrapRef.current !== null) {
        return bootstrapRef.current;
      }
      const bootstrap = (async () => {
        try {
          resolveBrowserIdentity(user);
          const projection = await loadTrustedSession();
          const session = resolveBrowserSession(user, projection);
          setState({ session, status: "authenticated" });
          return session;
        } catch (error) {
          await client.removeUser();
          setState(
            errorState(
              error instanceof BrowserIdentityError
                ? "identity_not_allowed"
                : "session_bootstrap_failed",
            ),
          );
          return null;
        }
      })();
      bootstrapRef.current = bootstrap;
      void bootstrap.finally(() => {
        if (bootstrapRef.current === bootstrap) {
          bootstrapRef.current = null;
        }
      });
      return bootstrap;
    },
    [client, loadTrustedSession],
  );

  const expireSession = useCallback(
    async (errorCode: AuthenticationErrorCode) => {
      await client.removeUser();
      setState({ errorCode, status: "session_expired" });
    },
    [client],
  );

  useEffect(() => {
    let active = true;

    const onUserLoaded = (user: User) => {
      if (active) {
        void acceptUser(user);
      }
    };
    const onUserUnloaded = () => {
      if (active) {
        setState({ status: "unauthenticated" });
      }
    };
    const onSessionEnded = () => {
      if (active) {
        void expireSession("session_renewal_failed");
      }
    };

    const unsubscribeUserLoaded = client.events.addUserLoaded(onUserLoaded);
    const unsubscribeUserUnloaded = client.events.addUserUnloaded(onUserUnloaded);
    const unsubscribeTokenExpired = client.events.addAccessTokenExpired(onSessionEnded);
    const unsubscribeSilentRenewError = client.events.addSilentRenewError(onSessionEnded);
    const unsubscribeUserSignedOut = client.events.addUserSignedOut(onSessionEnded);

    void (async () => {
      try {
        await client.clearStaleState();
        const user = await client.getUser();
        if (!active) {
          return;
        }
        if (user === null) {
          setState({ status: "unauthenticated" });
          return;
        }
        await acceptUser(user);
      } catch {
        if (active) {
          await client.removeUser();
          setState(errorState("signin_failed"));
        }
      }
    })();

    return () => {
      active = false;
      unsubscribeUserLoaded();
      unsubscribeUserUnloaded();
      unsubscribeTokenExpired();
      unsubscribeSilentRenewError();
      unsubscribeUserSignedOut();
    };
  }, [acceptUser, client, expireSession]);

  const signIn = useCallback(
    async (returnUrl?: string) => {
      setState({ status: "authenticating" });
      try {
        await client.signinRedirect({
          state: { returnUrl: safeReturnUrl(returnUrl) } satisfies SignInState,
        });
      } catch {
        setState(errorState("signin_failed"));
      }
    },
    [client],
  );

  const invalidateSession = useCallback(
    () => expireSession("session_renewal_failed"),
    [expireSession],
  );

  const completeSignIn = useCallback(async () => {
    try {
      const user = await client.signinRedirectCallback();
      const session = await acceptUser(user);
      if (session === null) {
        throw new BrowserIdentityError();
      }
      return safeReturnUrl((user.state as SignInState | undefined)?.returnUrl);
    } catch {
      await client.removeUser();
      setState((current) =>
        current.status === "error" ? current : errorState("callback_failed"),
      );
      throw new Error("Authentication callback failed");
    }
  }, [acceptUser, client]);

  const signOut = useCallback(async () => {
    setState({ status: "signing_out" });
    try {
      await client.signoutRedirect();
    } catch {
      await client.removeUser();
      setState(errorState("logout_failed"));
    }
  }, [client]);

  const completeSignOut = useCallback(async () => {
    try {
      await client.signoutRedirectCallback();
      await client.removeUser();
      setState({ status: "unauthenticated" });
    } catch {
      await client.removeUser();
      setState(errorState("logout_failed"));
      throw new Error("Logout callback failed");
    }
  }, [client]);

  const value = useMemo<AuthenticationContextValue>(
    () => ({
      ...state,
      can: (capability) =>
        state.status === "authenticated" &&
        state.session !== undefined &&
        hasCapability(state.session, capability),
      completeSignIn,
      completeSignOut,
      invalidateSession,
      signIn,
      signOut,
    }),
    [completeSignIn, completeSignOut, invalidateSession, signIn, signOut, state],
  );

  return <AuthenticationContext.Provider value={value}>{children}</AuthenticationContext.Provider>;
}
