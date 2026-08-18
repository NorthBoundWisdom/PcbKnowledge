"""Git-native PcbKnowledge core.

The canonical state lives in self-contained knowledge workspace files. This
package deliberately has no database, network identity, object-store, or
container dependency.
"""

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityKind,
    EntityRecord,
    Evidence,
    EvidenceAnchor,
    FactRecord,
    FactType,
    LicenseClass,
    ParameterLimitKind,
    ParameterLimitPayload,
    RecordStatus,
    ReviewAction,
    ReviewDecision,
    ReviewEvent,
    SourceLocation,
    SourceRecord,
    SourceType,
)
from pcbknowledge.git_native.store import (
    AuthoritySnapshot,
    ChangeScope,
    FactConflict,
    KnowledgeRepository,
)
from pcbknowledge.git_native.workspace import (
    SCHEMA_CONTRACT,
    WORKSPACE_FORMAT,
    WORKSPACE_MANIFEST_PATH,
    WorkspaceError,
    WorkspaceInitialization,
    WorkspaceManifest,
    WorkspaceValidation,
    initialize_workspace,
    validate_workspace,
    validate_workspace_ref,
)

__all__ = [
    "AuthoritySnapshot",
    "ChangeScope",
    "ComponentPinPayload",
    "EntityKind",
    "EntityRecord",
    "Evidence",
    "EvidenceAnchor",
    "FactConflict",
    "FactRecord",
    "FactType",
    "KnowledgeRepository",
    "LicenseClass",
    "ParameterLimitKind",
    "ParameterLimitPayload",
    "RecordStatus",
    "ReviewAction",
    "ReviewDecision",
    "ReviewEvent",
    "SCHEMA_CONTRACT",
    "SourceLocation",
    "SourceRecord",
    "SourceType",
    "WORKSPACE_FORMAT",
    "WORKSPACE_MANIFEST_PATH",
    "WorkspaceError",
    "WorkspaceInitialization",
    "WorkspaceManifest",
    "WorkspaceValidation",
    "initialize_workspace",
    "validate_workspace",
    "validate_workspace_ref",
]
