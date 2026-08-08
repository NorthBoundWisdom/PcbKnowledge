import type { RuntimeConfig } from "../config/runtime-config";
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
}

/**
 * This is the only application seam allowed to wrap generated transport code.
 * Route components consume feature hooks built on this boundary, never fetch.
 */
export function createApiClientBoundary(config: RuntimeConfig): ApiClientBoundary {
  return Object.freeze({
    apiBaseUrl: config.apiBaseUrl,
    contractSha256: generatedContractSha256,
    source: "generated-openapi" as const,
    transport: createGeneratedApiClient(config.apiBaseUrl),
  });
}
