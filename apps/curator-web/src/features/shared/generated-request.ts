import { BrowserAuthenticationRequiredError } from "../../api/client-boundary";
import type { RouteFailureKind } from "./RouteStatePanel";

export type FeatureRequestFailureKind =
  | "conflict"
  | "file_rejected"
  | "forbidden"
  | "network"
  | "not_found"
  | "service_unavailable"
  | "session_expired"
  | "unexpected";

export class FeatureRequestError extends Error {
  readonly kind: FeatureRequestFailureKind;
  readonly status?: number;

  constructor(kind: FeatureRequestFailureKind, status?: number) {
    super(`Generated API request failed with bounded category: ${kind}`);
    this.kind = kind;
    this.name = "FeatureRequestError";
    this.status = status;
  }
}

interface GeneratedResult<T> {
  readonly data?: T;
  readonly response: Response;
}

type InvalidateSession = () => Promise<void>;

function classifyStatus(status: number): FeatureRequestFailureKind {
  if (status === 401) return "session_expired";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 413 || status === 415 || status === 422) return "file_rejected";
  if (status === 502 || status === 503 || status === 504) return "service_unavailable";
  return "unexpected";
}

export async function runGeneratedRequest<T>(
  request: () => Promise<GeneratedResult<T>>,
  invalidateSession: InvalidateSession,
): Promise<T> {
  let result: GeneratedResult<T>;
  try {
    result = await request();
  } catch (error) {
    if (error instanceof BrowserAuthenticationRequiredError) {
      await invalidateSession();
      throw new FeatureRequestError("session_expired");
    }
    if (error instanceof FeatureRequestError) {
      throw error;
    }
    throw new FeatureRequestError("network");
  }

  if (result.response.ok && result.data !== undefined) {
    return result.data;
  }
  const kind = classifyStatus(result.response.status);
  if (kind === "session_expired") {
    await invalidateSession();
  }
  throw new FeatureRequestError(kind, result.response.status);
}

export function toRouteFailureKind(error: unknown): RouteFailureKind {
  if (!(error instanceof FeatureRequestError)) return "unexpected";
  if (error.kind === "forbidden") return "forbidden";
  if (error.kind === "not_found") return "not_found";
  if (error.kind === "session_expired") return "session_expired";
  if (error.kind === "network" || error.kind === "service_unavailable") {
    return "service_unavailable";
  }
  return "unexpected";
}
