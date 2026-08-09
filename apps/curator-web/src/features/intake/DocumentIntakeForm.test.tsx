import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentIntakeForm } from "./DocumentIntakeForm";
import type { IntakeFormChoices } from "./intake-view-models";

const projectId = "00000000-0000-7000-8000-000000000021";
const choices: IntakeFormChoices = {
  accessScopes: [{ id: "scope-1", label: "Project evidence", projectId }],
  licensePolicies: [
    {
      accessScopeId: "scope-1",
      allowsParsing: true,
      allowsRawAccess: true,
      id: "license-1",
      label: "Open reference",
      secondary: "PUBLIC_REFERENCE",
    },
  ],
  projects: [{ id: projectId, label: "Component Research" }],
  sourceOrganizations: [{ id: "source-1", label: "Example Semiconductor" }],
};

describe("DocumentIntakeForm", () => {
  it("requires a PDF and explicit metadata confirmation", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <DocumentIntakeForm activity={{ phase: "idle" }} choices={choices} onSubmit={onSubmit} />,
    );

    await user.click(screen.getByRole("button", { name: "Upload and verify PDF" }));

    expect(await screen.findByText("Select exactly one PDF file.")).toBeVisible();
    expect(screen.getByText("Enter a document title.")).toBeVisible();
    expect(screen.getByText("Confirm the intake metadata before uploading.")).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits one normalized presentation model", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <DocumentIntakeForm activity={{ phase: "idle" }} choices={choices} onSubmit={onSubmit} />,
    );

    const file = new File(["%PDF-1.7\n%%EOF"], "reference.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("PDF file"), file);
    await user.type(screen.getByLabelText("Title"), "  Reference Datasheet  ");
    await user.type(screen.getByLabelText("Document number (optional)"), " DS-100 ");
    await user.type(screen.getByLabelText("Revision"), " A ");
    await user.click(screen.getByLabelText("Source organization"));
    await user.click(screen.getByRole("option", { name: "Example Semiconductor" }));
    await user.click(screen.getByLabelText("Access scope"));
    await user.click(screen.getByRole("option", { name: "Project evidence" }));
    await user.click(screen.getByLabelText("License policy"));
    await user.click(screen.getByRole("option", { name: /Open reference/ }));
    await user.click(
      screen.getByLabelText(/I confirmed the source, project scope, license policy/),
    );
    await user.click(screen.getByRole("button", { name: "Upload and verify PDF" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        accessScopeId: "scope-1",
        documentNumber: "DS-100",
        file,
        licensePolicyId: "license-1",
        projectId,
        revisionLabel: "A",
        sourceOrganizationId: "source-1",
        title: "Reference Datasheet",
      }),
    );
  });

  it("shows bounded upload progress and prevents duplicate submit", () => {
    render(
      <DocumentIntakeForm
        activity={{ percent: 35, phase: "uploading" }}
        choices={choices}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByRole("progressbar", { name: "Document upload progress" })).toHaveAttribute(
      "aria-valuenow",
      "35",
    );
    expect(screen.getByRole("button", { name: "Upload and verify PDF" })).toBeDisabled();
  });
});
