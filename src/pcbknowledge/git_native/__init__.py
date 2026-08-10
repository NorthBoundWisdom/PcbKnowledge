"""Git-native PcbKnowledge core.

The canonical state lives in repository files. This package deliberately has
no database, network identity, object-store, or container dependency.
"""

from pcbknowledge.git_native.model import (
    Evidence,
    KnowledgeRecord,
    LicenseClass,
    RecordStatus,
    ReviewAction,
    ReviewDecision,
    ReviewEvent,
    Source,
)
from pcbknowledge.git_native.store import ChangeScope, KnowledgeRepository

__all__ = [
    "ChangeScope",
    "Evidence",
    "KnowledgeRecord",
    "KnowledgeRepository",
    "LicenseClass",
    "RecordStatus",
    "ReviewAction",
    "ReviewDecision",
    "ReviewEvent",
    "Source",
]
