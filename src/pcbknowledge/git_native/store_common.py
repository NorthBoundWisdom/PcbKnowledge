"""Atomic Git-native authority store for Source/Entity/Fact records and evidence."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Mapping

import fcntl

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityKind,
    EntityRecord,
    Evidence,
    FactRecord,
    FactType,
    LicenseClass,
    ParameterLimitPayload,
    PreparedBy,
    RecordStatus,
    RecordTransitionError,
    RecordValidationError,
    SourceRecord,
    SourceType,
    deterministic_entity_id,
    deterministic_fact_id,
    deterministic_record_id,
)

MAX_RECORD_BYTES = 1_000_000
MAX_PDF_BYTES = 64 * 1024 * 1024
_SOURCE_FILENAME = re.compile(r"pk_[0-9a-f]{24,32}\.json\Z")
_ENTITY_FILENAME = re.compile(r"ent_[0-9a-f]{24,32}\.json\Z")
_FACT_FILENAME = re.compile(r"fact_[0-9a-f]{24,32}\.json\Z")
_EVIDENCE_PATH = re.compile(r"evidence/sha256/(?P<prefix>[0-9a-f]{2})/(?P<digest>[0-9a-f]{64})\.pdf\Z")
_DATA_ROOTS = ("knowledge/", "evidence/")

class RepositoryError(RuntimeError):
    """Base error for repository operations."""

class RecordNotFoundError(RepositoryError):
    """A requested authority object does not exist."""

class RecordConflictError(RepositoryError):
    """An optimistic or idempotent write conflicts with current authority."""

class EvidenceError(RepositoryError):
    """Evidence bytes are malformed or inconsistent."""

class ChangeScope(StrEnum):
    CLEAN = "CLEAN"
    DATA_ONLY = "DATA_ONLY"
    CODE_ONLY = "CODE_ONLY"
    MIXED = "MIXED"

@dataclass(frozen=True, slots=True)
class GitChanges:
    status_lines: tuple[str, ...]
    tracked_diff: str
    untracked_preview: str
    @property
    def count(self) -> int:
        return len(self.status_lines)

@dataclass(frozen=True, slots=True)
class FactConflict:
    semantic_key: tuple[object, ...]
    fact_ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class AuthoritySnapshot:
    sources: tuple[SourceRecord, ...]
    entities: tuple[EntityRecord, ...]
    facts: tuple[FactRecord, ...]
    conflicts: tuple[FactConflict, ...] = ()
    ref: str | None = None
    commit: str | None = None
    @property
    def published_sources(self) -> tuple[SourceRecord, ...]:
        return tuple(item for item in self.sources if item.status is RecordStatus.APPROVED)
    @property
    def published_facts(self) -> tuple[FactRecord, ...]:
        return tuple(item for item in self.facts if item.status is RecordStatus.APPROVED)
    def __len__(self) -> int:
        return len(self.sources) + len(self.entities) + len(self.facts)
