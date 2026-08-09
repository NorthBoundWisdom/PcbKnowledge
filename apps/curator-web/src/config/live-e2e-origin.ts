export const liveE2eBaseUrlVariable = "PCBKNOWLEDGE_E2E_LIVE_BASE_URL";

const loopbackOrigin = /^http:\/\/(?:localhost|127\.0\.0\.1):([0-9]{1,5})\/?$/u;

export function resolveLiveE2eBaseUrl(
  source: Readonly<Record<string, string | undefined>>,
): string | undefined {
  if (!(liveE2eBaseUrlVariable in source)) {
    return undefined;
  }
  const configured = source[liveE2eBaseUrlVariable]?.trim();
  const match = configured === undefined ? null : loopbackOrigin.exec(configured);
  const port = match?.[1] === undefined ? Number.NaN : Number(match[1]);
  if (configured === undefined || match === null || port < 1 || port > 65_535) {
    throw new Error(
      `${liveE2eBaseUrlVariable} must be an exact loopback HTTP origin with an explicit valid port`,
    );
  }
  return new URL(configured).origin;
}

export function isLoopbackHttpUrl(value: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return false;
  }
  const port = Number(parsed.port);
  return (
    parsed.protocol === "http:" &&
    (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") &&
    /^[0-9]{1,5}$/u.test(parsed.port) &&
    port >= 1 &&
    port <= 65_535 &&
    parsed.username.length === 0 &&
    parsed.password.length === 0
  );
}
