"""Git-native PcbKnowledge core.

The canonical state lives in repository files.  This package deliberately has
no database, network identity, object-store, or container dependency.
"""

from pcbknowledge.git_native.model import (
    Evidence,
    KnowledgeRecord,
    LicenseClass,
    RecordStatus,
    ReviewDecision,
    Source,
)
from pcbknowledge.git_native.store import KnowledgeRepository

__all__ = [
    "Evidence",
    "KnowledgeRecord",
    "KnowledgeRepository",
    "LicenseClass",
    "RecordStatus",
    "ReviewDecision",
    "Source",
]
