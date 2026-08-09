import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentRevisionPageView } from "./DocumentRevisionPageView";

const revision = {
  byteSize: 1_048_576,
  createdAt: "2026-08-09 18:00",
  documentId: "document-1",
  documentNumber: "DS-100",
  id: "revision-1",
  mediaType: "application/pdf",
  originalFilename: "reference.pdf",
  projectName: "Component Research",
  revisionLabel: "A",
  sha256: "a".repeat(64),
  sourceOrganizationName: "Example Semiconductor",
  state: "STORED",
  title: "Reference Datasheet",
} as const;

describe("DocumentRevisionPageView", () => {
  it("uses a non-disclosing not-found state", () => {
    render(
      <DocumentRevisionPageView
        download={{ status: "idle" }}
        onDownload={vi.fn()}
        state={{ kind: "not_found", status: "failed" }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Resource unavailable" })).toBeVisible();
    expect(screen.queryByText("Reference Datasheet")).not.toBeInTheDocument();
  });

  it("requests an audited original without rendering a permanent object URL", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    render(
      <DocumentRevisionPageView
        download={{ status: "idle" }}
        onDownload={onDownload}
        state={{ revision, status: "ready" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open authorized original" }));

    expect(onDownload).toHaveBeenCalledOnce();
    expect(screen.queryByRole("link", { name: /original/i })).not.toBeInTheDocument();
    expect(screen.getByText("a".repeat(64))).toBeVisible();
  });

  it("shows a bounded download failure", () => {
    render(
      <DocumentRevisionPageView
        download={{ status: "failed" }}
        onDownload={vi.fn()}
        state={{ revision, status: "ready" }}
      />,
    );

    expect(screen.getByText(/No anonymous or direct object path was used/)).toBeVisible();
  });
});
