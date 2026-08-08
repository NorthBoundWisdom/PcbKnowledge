import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createTestRouter } from "../app/router";
import { RootApplication } from "../app/RootApplication";
import { validEnvironment } from "../test/test-config";
import { loadRuntimeConfig, RuntimeConfigurationError } from "./runtime-config";

describe("runtime configuration", () => {
  it("normalizes valid public configuration", () => {
    const config = loadRuntimeConfig({
      ...validEnvironment,
      VITE_API_BASE_URL: "https://knowledge.example.test/api/v1/",
    });

    expect(config.apiBaseUrl).toBe("https://knowledge.example.test/api/v1");
    expect(config.oidc.clientId).toBe("pcbknowledge-curator-web");
  });

  it("fails closed when required configuration is missing", () => {
    expect(() => loadRuntimeConfig({})).toThrow(RuntimeConfigurationError);
  });

  it("rejects browser-exposed secrets", () => {
    expect(() =>
      loadRuntimeConfig({
        ...validEnvironment,
        VITE_OIDC_CLIENT_SECRET: "must-not-reach-a-browser",
      }),
    ).toThrow(RuntimeConfigurationError);
  });

  it("renders a diagnostic failure surface instead of the application shell", () => {
    render(<RootApplication environment={{}} router={createTestRouter(["/dashboard"])} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Configuration required");
    expect(screen.getByText(/VITE_API_BASE_URL/)).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Dashboard" })).not.toBeInTheDocument();
  });
});
