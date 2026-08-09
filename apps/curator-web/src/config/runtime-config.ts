import { z } from "zod";

const relativeOrHttpUrl = z.string().trim().min(1).refine(
  (value) => {
    if (value.startsWith("/")) {
      return !value.startsWith("//");
    }

    try {
      const url = new URL(value);
      return url.protocol === "https:" || url.protocol === "http:";
    } catch {
      return false;
    }
  },
  { message: "must be an absolute HTTP(S) URL or a root-relative path" },
);

const runtimeConfigSchema = z.object({
  VITE_API_BASE_URL: relativeOrHttpUrl,
  VITE_DEPLOYMENT_LABEL: z.string().trim().min(1).max(48).default("M2a Intake"),
  VITE_OIDC_CLIENT_ID: z.string().trim().min(1),
  VITE_OIDC_ISSUER_URL: relativeOrHttpUrl,
});

const forbiddenBrowserSecret = /(?:SECRET|PASSWORD|PRIVATE_KEY|ACCESS_TOKEN|REFRESH_TOKEN)$/i;

export interface RuntimeConfig {
  readonly apiBaseUrl: string;
  readonly deploymentLabel: string;
  readonly oidc: {
    readonly clientId: string;
    readonly issuerUrl: string;
  };
}

export class RuntimeConfigurationError extends Error {
  readonly problems: readonly string[];

  constructor(problems: readonly string[]) {
    super("Curator Web runtime configuration is invalid");
    this.name = "RuntimeConfigurationError";
    this.problems = problems;
  }
}

export function loadRuntimeConfig(source: Record<string, unknown>): RuntimeConfig {
  const exposedSecrets = Object.keys(source).filter(
    (key) => key.startsWith("VITE_") && forbiddenBrowserSecret.test(key),
  );

  if (exposedSecrets.length > 0) {
    throw new RuntimeConfigurationError(
      exposedSecrets.map((key) => `${key}: browser configuration must never contain secrets`),
    );
  }

  const parsed = runtimeConfigSchema.safeParse(source);
  if (!parsed.success) {
    throw new RuntimeConfigurationError(
      parsed.error.issues.map((issue) => `${issue.path.join(".") || "configuration"}: ${issue.message}`),
    );
  }

  return Object.freeze({
    apiBaseUrl: parsed.data.VITE_API_BASE_URL.replace(/\/$/, ""),
    deploymentLabel: parsed.data.VITE_DEPLOYMENT_LABEL,
    oidc: Object.freeze({
      clientId: parsed.data.VITE_OIDC_CLIENT_ID,
      issuerUrl: parsed.data.VITE_OIDC_ISSUER_URL.replace(/\/$/, ""),
    }),
  });
}
