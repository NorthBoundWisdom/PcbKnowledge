"""Git-native PcbKnowledge core.

The canonical state lives in repository files. This package deliberately has
no database, network identity, object-store, or container dependency.
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
    "SourceLocation",
    "SourceRecord",
    "SourceType",
]
