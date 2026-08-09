import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyRouteState, FailedRouteState, LoadingRouteState } from "./RouteStatePanel";

describe("route state panels", () => {
  it("announces loading without presenting stale content", () => {
    render(<LoadingRouteState label="Loading document revisions" />);

    expect(screen.getByRole("progressbar", { name: "Loading document revisions" })).toBeVisible();
  });

  it("renders an explicit empty state", () => {
    render(<EmptyRouteState description="Upload the first source PDF." title="No documents" />);

    expect(screen.getByRole("heading", { name: "No documents" })).toBeVisible();
    expect(screen.getByText("Upload the first source PDF.")).toBeVisible();
  });

  it("does not distinguish a missing resource from a hidden resource", () => {
    render(<FailedRouteState kind="not_found" />);

    expect(screen.getByRole("heading", { name: "Resource unavailable" })).toBeVisible();
    expect(screen.getByText(/does not exist or is not visible/)).toBeVisible();
  });

  it("offers a bounded retry for transient failures", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(<FailedRouteState kind="service_unavailable" onRetry={retry} />);

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(retry).toHaveBeenCalledOnce();
  });
});
