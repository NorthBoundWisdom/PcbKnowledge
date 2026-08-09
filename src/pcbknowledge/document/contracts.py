"""Typed HTTP contracts for the first document-intake vertical slice."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pcbknowledge.platform.authorization.models import LicenseClass
from pcbknowledge.platform.ids import UUID7
from pcbknowledge.platform.time import UTCDateTime


class UploadSessionProjectionState(StrEnum):
    """User-visible upload progress, including transient durable-job states."""

    RESERVED = "RESERVED"
    QUEUED = "QUEUED"
    VERIFYING = "VERIFYING"
    RETRYING = "RETRYING"
    STORED = "STORED"
    FAILED = "FAILED"


class ProjectOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    display_name: str


class AccessScopeOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    project_id: UUID7
    name: str


class LicensePolicyOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    access_scope_id: UUID7
    name: str
    license_class: LicenseClass
    allow_human_raw_access: bool
    allow_parse: bool


class SourceOrganizationOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    name: str
    authority_tier: str


class IntakeOptionsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    projects: tuple[ProjectOption, ...]
    access_scopes: tuple[AccessScopeOption, ...]
    license_policies: tuple[LicensePolicyOption, ...]
    source_organizations: tuple[SourceOrganizationOption, ...]


class CreateUploadSessionRequest(BaseModel):
    """Metadata intent bound before an untrusted browser upload is accepted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: UUID7
    access_scope_id: UUID7
    license_policy_id: UUID7
    source_organization_id: UUID7
    document_id: UUID7 | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    document_number: str | None = Field(default=None, min_length=1, max_length=255)
    revision_label: str = Field(min_length=1, max_length=128)
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(default="application/pdf", pattern=r"^application/pdf$")
    byte_size: int = Field(ge=1, le=268_435_456)

    @field_validator("title", "document_number", "revision_label", "original_filename")
    @classmethod
    def require_clean_display_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or "\r" in cleaned or "\n" in cleaned or "\x00" in cleaned:
            raise ValueError("display text must be a non-empty single line")
        return cleaned

    @model_validator(mode="after")
    def require_new_document_identity(self) -> Self:
        if self.document_id is None and self.title is None:
            raise ValueError("title is required when creating a new document")
        if self.document_id is not None and (
            self.title is not None or self.document_number is not None
        ):
            raise ValueError("existing document uploads cannot replace document metadata")
        return self


class CompleteUploadSessionRequest(BaseModel):
    """Optional client digest is only an additional mismatch guard."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class PresignedUploadResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    headers: dict[str, str]
    expires_in_seconds: int = Field(ge=1, le=3600)


class UploadSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    document_id: UUID7
    revision_id: UUID7
    project_id: UUID7
    state: UploadSessionProjectionState
    created_at: UTCDateTime
    updated_at: UTCDateTime
    job_id: UUID7 | None = None
    actual_sha256: str | None = None
    failure_code: str | None = None
    upload: PresignedUploadResponse | None = None
    replayed: bool = False


class ProjectSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    display_name: str


class RevisionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    revision_label: str
    state: str
    created_at: UTCDateTime


class DocumentListItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    project: ProjectSummary
    title: str
    document_number: str | None = None
    latest_revision: RevisionSummary


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[DocumentListItem, ...]
    next_cursor: UUID7 | None = None


class SourceOrganizationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    name: str


class DocumentRevisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID7
    document_id: UUID7
    project: ProjectSummary
    title: str
    document_number: str | None = None
    revision_label: str
    state: str
    source_organization: SourceOrganizationSummary
    original_filename: str
    media_type: str
    sha256: str
    byte_size: int
    created_at: UTCDateTime


class OriginalDownloadResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    revision_id: UUID7
    audit_event_id: UUID7
    url: str
    expires_in_seconds: int = Field(ge=1, le=3600)
