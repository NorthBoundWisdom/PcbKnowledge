import { createContext } from "react";

import type {
  AuthenticationErrorCode,
  AuthenticationStatus,
  BrowserCapability,
  BrowserSession,
} from "./auth-types";

export interface AuthenticationContextValue {
  readonly errorCode?: AuthenticationErrorCode;
  readonly session?: BrowserSession;
  readonly status: AuthenticationStatus;
  can(capability: BrowserCapability): boolean;
  completeSignIn(): Promise<string>;
  completeSignOut(): Promise<void>;
  signIn(returnUrl?: string): Promise<void>;
  signOut(): Promise<void>;
}

export const AuthenticationContext = createContext<AuthenticationContextValue | null>(null);
