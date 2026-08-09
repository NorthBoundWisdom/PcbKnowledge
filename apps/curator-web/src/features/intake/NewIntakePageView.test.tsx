import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NewIntakePageView } from "./NewIntakePageView";

describe("NewIntakePageView", () => {
  it("shows an explicit loading state before rendering protected choices", () => {
    render(
      <NewIntakePageView
        activity={{ phase: "idle" }}
        onSubmit={vi.fn()}
        options={{ status: "loading" }}
      />,
    );

    expect(
      screen.getByRole("progressbar", {
        name: "Loading authorized project, source, scope, and license choices",
      }),
    ).toBeVisible();
    expect(screen.queryByLabelText("PDF file")).not.toBeInTheDocument();
  });

  it("fails closed when no authorized intake configuration is available", () => {
    render(
      <NewIntakePageView
        activity={{ phase: "idle" }}
        onSubmit={vi.fn()}
        options={{ kind: "forbidden", status: "failed" }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Access denied" })).toBeVisible();
    expect(screen.queryByLabelText("PDF file")).not.toBeInTheDocument();
  });
});
