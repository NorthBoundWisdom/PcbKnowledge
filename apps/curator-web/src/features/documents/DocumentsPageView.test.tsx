import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DocumentsPageView } from "./DocumentsPageView";

function renderPage(properties: Parameters<typeof DocumentsPageView>[0]) {
  render(
    <MemoryRouter>
      <DocumentsPageView {...properties} />
    </MemoryRouter>,
  );
}

describe("DocumentsPageView", () => {
  it("does not load data before a project is selected", () => {
    renderPage({ projectSelected: false, state: { status: "loading" } });

    expect(screen.getByRole("heading", { name: "Select a project" })).toBeVisible();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("renders the typed document projection and revision link", () => {
    renderPage({
      projectSelected: true,
      state: {
        hasNextPage: false,
        items: [
          {
            documentId: "document-1",
            documentNumber: "DS-100",
            projectName: "Component Research",
            revisionCreatedAt: "2026-08-09 18:00",
            revisionId: "revision-1",
            revisionLabel: "A",
            state: "STORED",
            title: "Reference Datasheet",
          },
        ],
        loadingNextPage: false,
        onLoadNextPage: vi.fn(),
        status: "ready",
      },
    });

    expect(screen.getByRole("table", { name: "Documents" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Reference Datasheet" })).toHaveAttribute(
      "href",
      "/documents/revision-1",
    );
    expect(screen.getByText("DS-100")).toBeVisible();
  });

  it("retries a transient list failure", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    renderPage({
      projectSelected: true,
      state: { kind: "service_unavailable", onRetry: retry, status: "failed" },
    });

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(retry).toHaveBeenCalledOnce();
  });
});
