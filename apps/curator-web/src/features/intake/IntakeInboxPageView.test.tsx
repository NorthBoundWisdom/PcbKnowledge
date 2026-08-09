import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { IntakeInboxPageView } from "./IntakeInboxPageView";

function renderInbox(items: Parameters<typeof IntakeInboxPageView>[0]["items"]) {
  render(
    <MemoryRouter>
      <IntakeInboxPageView items={items} />
    </MemoryRouter>,
  );
}

describe("IntakeInboxPageView", () => {
  it("offers the first upload from an explicit empty state", () => {
    renderInbox([]);

    expect(screen.getByRole("heading", { name: "No recent intake" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Upload the first PDF" })).toHaveAttribute(
      "href",
      "/intake/new",
    );
  });

  it("shows a bounded failure category without reflecting a worker payload", () => {
    renderInbox([
      {
        failureCode: "untrusted-worker-detail",
        id: "upload-1",
        revisionId: "revision-1",
        state: "FAILED",
        title: "Reference datasheet",
        updatedAt: "2026-08-09 18:00",
      },
    ]);

    expect(screen.getByText("FAILED")).toBeVisible();
    expect(screen.getByText(/Verification did not complete/)).toBeVisible();
    expect(screen.queryByText("untrusted-worker-detail")).not.toBeInTheDocument();
  });
});
