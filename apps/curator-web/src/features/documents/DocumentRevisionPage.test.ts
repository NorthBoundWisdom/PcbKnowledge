import { describe, expect, it, vi } from "vitest";

import { FeatureRequestError } from "../shared/generated-request";
import { navigateToAuthorizedOriginal } from "./authorized-original-navigation";

describe("authorized original navigation", () => {
  it("uses browser navigation instead of fetching the private object", () => {
    const navigate = vi.fn();

    navigateToAuthorizedOriginal(
      "https://objects.example.test/content/reference.pdf?signature=one-time",
      navigate,
    );

    expect(navigate).toHaveBeenCalledWith(
      "https://objects.example.test/content/reference.pdf?signature=one-time",
    );
  });

  it.each(["javascript:alert(1)", "data:application/pdf,unsafe", "/relative-object"])(
    "rejects a non-http(s) or relative target: %s",
    (target) => {
      expect(() => navigateToAuthorizedOriginal(target, vi.fn())).toThrow(FeatureRequestError);
    },
  );
});
