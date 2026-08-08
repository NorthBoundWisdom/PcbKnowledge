import type { RuntimeConfig } from "../config/runtime-config";
import {
  resolveBrowserIdentity,
  type AuthClient,
  type TrustedSessionProjection,
} from "../auth/auth-types";
import {
  createGeneratedApiClient,
  generatedContractSha256,
  type GeneratedApiClient,
} from "./generated";

export type PcbKnowledgeApiClient = GeneratedApiClient;

export interface ApiClientBoundary {
  readonly apiBaseUrl: string;
  readonly contractSha256: string;
  readonly source: "generated-openapi";
  readonly transport: PcbKnowledgeApiClient;
  loadTrustedSession(): Promise<TrustedSessionProjection>;
}

export class BrowserAuthenticationRequiredError extends Error {
  constructor() {
    super("An active, approved in-memory browser session is required");
    this.name = "BrowserAuthenticationRequiredError";
  }
}

export class TrustedSessionBootstrapError extends Error {
  constructor() {
    super("The trusted application session could not be established");
    this.name = "TrustedSessionBootstrapError";
  }
}

/**
 * This is the only application seam allowed to wrap generated transport code.
 * Route components consume feature hooks built on this boundary, never fetch.
 */
export function createApiClientBoundary(
  config: RuntimeConfig,
  authClient: Pick<AuthClient, "getUser">,
): ApiClientBoundary {
  const transport = createGeneratedApiClient(config.apiBaseUrl);
  transport.use({
    async onRequest({ request }) {
      const user = await authClient.getUser();
      if (user === null || user.expired || user.access_token.length === 0) {
        throw new BrowserAuthenticationRequiredError();
      }
      try {
        resolveBrowserIdentity(user);
      } catch {
        throw new BrowserAuthenticationRequiredError();
      }
      request.headers.set("Authorization", `Bearer ${user.access_token}`);
      return request;
    },
  });

  return Object.freeze({
    apiBaseUrl: config.apiBaseUrl,
    contractSha256: generatedContractSha256,
    async loadTrustedSession() {
      const result = await transport.GET("/session");
      if (!result.response.ok || result.data === undefined) {
        throw new TrustedSessionBootstrapError();
      }
      return result.data;
    },
    source: "generated-openapi" as const,
    transport,
  });
}
