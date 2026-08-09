import { NewIntakePageView } from "./NewIntakePageView";
import { useDocumentUpload } from "./use-document-upload";
import { useIntakeOptions } from "./use-intake-options";
import { useProjectSelection } from "../workspace/use-project-selection";

export function NewIntakePage() {
  const options = useIntakeOptions();
  const project = useProjectSelection();
  const upload = useDocumentUpload();

  return (
    <NewIntakePageView
      activity={upload.activity}
      initialProjectId={project.selectedProjectId}
      onSubmit={upload.submit}
      options={options}
    />
  );
}
