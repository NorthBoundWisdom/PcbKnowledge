import { FeatureRequestError } from "../shared/generated-request";

export function navigateToAuthorizedOriginal(
  url: string,
  navigate: (target: string) => void = (target) => window.location.assign(target),
): void {
  let target: URL;
  try {
    target = new URL(url);
  } catch {
    throw new FeatureRequestError("unexpected");
  }
  if (target.protocol !== "http:" && target.protocol !== "https:") {
    throw new FeatureRequestError("unexpected");
  }
  navigate(target.href);
}
