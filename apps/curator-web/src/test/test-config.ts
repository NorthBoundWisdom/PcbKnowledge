import type { RuntimeConfig } from "../config/runtime-config";

export const validEnvironment = {
  VITE_API_BASE_URL: "/api/v1",
  VITE_DEPLOYMENT_LABEL: "Test M1",
  VITE_OIDC_CLIENT_ID: "pcbknowledge-curator-web",
  VITE_OIDC_ISSUER_URL: "https://identity.example.test/realms/pcbknowledge",
} as const;

export const validRuntimeConfig: RuntimeConfig = {
  apiBaseUrl: "/api/v1",
  deploymentLabel: "Test M1",
  oidc: {
    clientId: "pcbknowledge-curator-web",
    issuerUrl: "https://identity.example.test/realms/pcbknowledge",
  },
};
