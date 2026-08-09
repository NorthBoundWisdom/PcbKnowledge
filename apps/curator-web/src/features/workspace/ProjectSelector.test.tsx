import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProjectSelector } from "./ProjectSelector";

const projects = [
  { id: "00000000-0000-7000-8000-000000000021", label: "Component Research" },
  { id: "00000000-0000-7000-8000-000000000022", label: "Process Library" },
] as const;

describe("ProjectSelector", () => {
  it("selects a named project with the keyboard-accessible combobox", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ProjectSelector onChange={onChange} projects={projects} />);

    await user.click(screen.getByRole("combobox", { name: "Project" }));
    await user.click(screen.getByRole("option", { name: "Process Library" }));

    expect(onChange).toHaveBeenCalledWith(projects[1].id);
  });

  it("shows an explicit disabled state when the session grants no projects", () => {
    render(<ProjectSelector onChange={vi.fn()} projects={[]} />);

    expect(screen.getByRole("combobox", { name: "Project" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByText("No project access")).toBeVisible();
  });
});
