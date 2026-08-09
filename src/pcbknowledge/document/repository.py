"""PostgreSQL repositories for tenant-scoped immutable documents and intake."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, desc, select, text
from sqlalchemy.orm import Session, aliased

from pcbknowledge.document.errors import (
    DocumentNotFoundError,
    UploadSessionNotFoundError,
)
from pcbknowledge.document.models import (
    Document,
    DocumentAsset,
    DocumentAssetKind,
    DocumentRevision,
    DocumentRevisionState,
    UploadSession,
    UploadSessionState,
)
from pcbknowledge.platform.authorization.models import (
    AccessScope,
    LicensePolicy,
    SourceOrganization,
)
from pcbknowledge.platform.identity.models import Project
from pcbknowledge.platform.jobs.models import KnowledgeJob
from pcbknowledge.platform.storage.models import (
    ObjectAsset,
    ObjectAssetState,
    StagingUploadReservation,
)
from pcbknowledge.platform.time import utc_now


@dataclass(frozen=True, slots=True)
class UploadSessionView:
    upload: UploadSession
    reservation: StagingUploadReservation
    job: KnowledgeJob | None


@dataclass(frozen=True, slots=True)
class DocumentListRow:
    document: Document
    project: Project
    revision: DocumentRevision
    access_scope: AccessScope
    license_policy: LicensePolicy


@dataclass(frozen=True, slots=True)
class DocumentRevisionRow:
    document: Document
    project: Project
    revision: DocumentRevision
    source_organization: SourceOrganization
    access_scope: AccessScope
    license_policy: LicensePolicy
    document_asset: DocumentAsset
    object_asset: ObjectAsset


class DocumentRepository:
    """All queries include explicit tenant keys in addition to FORCE RLS."""

    @staticmethod
    def acquire_idempotency_lock(
        session: Session,
        *,
        organization_id: UUID,
        actor_subject_id: UUID,
        idempotency_key: str,
    ) -> None:
        session.execute(
            text(
                "SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(:lock_key, 0))"
            ),
            {"lock_key": f"upload-session:{organization_id}:{actor_subject_id}:{idempotency_key}"},
        )

    @staticmethod
    def acquire_revision_intent_lock(
        session: Session,
        *,
        organization_id: UUID,
        document_id: UUID,
        revision_label: str,
    ) -> None:
        session.execute(
            text(
                "SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(:lock_key, 0))"
            ),
            {"lock_key": (f"document-revision:{organization_id}:{document_id}:{revision_label}")},
        )

    @staticmethod
    def find_upload_by_idempotency(
        session: Session,
        *,
        organization_id: UUID,
        actor_subject_id: UUID,
        idempotency_key: str,
    ) -> UploadSession | None:
        return session.scalar(
            select(UploadSession).where(
                UploadSession.organization_id == organization_id,
                UploadSession.created_by_subject_id == actor_subject_id,
                UploadSession.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def add_upload(session: Session, upload: UploadSession) -> UploadSession:
        session.add(upload)
        session.flush((upload,))
        return upload

    @staticmethod
    def get_upload_view(
        session: Session,
        *,
        organization_id: UUID,
        upload_id: UUID,
        actor_subject_id: UUID | None = None,
        for_update: bool = False,
    ) -> UploadSessionView:
        statement = (
            select(UploadSession, StagingUploadReservation, KnowledgeJob)
            .join(
                StagingUploadReservation,
                (StagingUploadReservation.id == UploadSession.id)
                & (StagingUploadReservation.organization_id == UploadSession.organization_id),
            )
            .outerjoin(
                KnowledgeJob,
                (KnowledgeJob.id == UploadSession.completion_job_id)
                & (KnowledgeJob.organization_id == UploadSession.organization_id),
            )
            .where(
                UploadSession.id == upload_id,
                UploadSession.organization_id == organization_id,
            )
        )
        if actor_subject_id is not None:
            statement = statement.where(UploadSession.created_by_subject_id == actor_subject_id)
        if for_update:
            statement = statement.with_for_update(of=UploadSession)
        row = session.execute(statement).one_or_none()
        if row is None:
            raise UploadSessionNotFoundError()
        return UploadSessionView(upload=row[0], reservation=row[1], job=row[2])

    @staticmethod
    def get_document(
        session: Session,
        *,
        organization_id: UUID,
        project_id: UUID,
        document_id: UUID,
    ) -> Document:
        document = session.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.project_id == project_id,
            )
        )
        if document is None:
            raise DocumentNotFoundError()
        return document

    @staticmethod
    def revision_label_exists(
        session: Session,
        *,
        document_id: UUID,
        revision_label: str,
    ) -> bool:
        return (
            session.scalar(
                select(DocumentRevision.id).where(
                    DocumentRevision.document_id == document_id,
                    DocumentRevision.revision_label == revision_label,
                )
            )
            is not None
        )

    @staticmethod
    def active_revision_upload_exists(
        session: Session,
        *,
        organization_id: UUID,
        document_id: UUID,
        revision_label: str,
    ) -> bool:
        return (
            session.scalar(
                select(UploadSession.id).where(
                    UploadSession.organization_id == organization_id,
                    UploadSession.target_document_id == document_id,
                    UploadSession.revision_label == revision_label,
                    UploadSession.state != UploadSessionState.FAILED.value,
                )
            )
            is not None
        )

    @staticmethod
    def mark_queued(
        upload: UploadSession,
        *,
        job_id: UUID,
        expected_sha256: str | None,
        now: datetime,
    ) -> None:
        upload.state = UploadSessionState.QUEUED.value
        upload.completion_job_id = job_id
        upload.expected_sha256 = expected_sha256
        upload.updated_at = now

    @staticmethod
    def store_verified_records(
        session: Session,
        *,
        upload: UploadSession,
        object_asset: ObjectAsset,
        actual_sha256: str,
        now: datetime,
    ) -> tuple[Document, DocumentRevision, DocumentAsset]:
        if upload.creates_document:
            document = Document(
                id=upload.target_document_id,
                organization_id=upload.organization_id,
                project_id=upload.project_id,
                title=upload.title,
                document_number=upload.document_number,
                created_by_subject_id=upload.created_by_subject_id,
                created_at=upload.created_at,
            )
            session.add(document)
            session.flush((document,))
        else:
            document = DocumentRepository.get_document(
                session,
                organization_id=upload.organization_id,
                project_id=upload.project_id,
                document_id=upload.target_document_id,
            )
            if document.title != upload.title or document.document_number != upload.document_number:
                raise DocumentNotFoundError()

        revision = DocumentRevision(
            id=upload.target_revision_id,
            organization_id=upload.organization_id,
            project_id=upload.project_id,
            document_id=upload.target_document_id,
            source_organization_id=upload.source_organization_id,
            access_scope="PROJECT",
            access_scope_id=upload.access_scope_id,
            license_policy_id=upload.license_policy_id,
            revision_label=upload.revision_label,
            original_filename=upload.original_filename,
            media_type=upload.media_type,
            state=DocumentRevisionState.STORED.value,
            created_by_subject_id=upload.created_by_subject_id,
            created_at=now,
        )
        session.add(revision)
        session.flush((revision,))
        relation = DocumentAsset(
            organization_id=upload.organization_id,
            project_id=upload.project_id,
            revision_id=revision.id,
            object_asset_id=object_asset.id,
            asset_kind=DocumentAssetKind.ORIGINAL.value,
            created_at=now,
        )
        session.add(relation)
        session.flush((relation,))

        upload.state = UploadSessionState.STORED.value
        upload.actual_sha256 = actual_sha256
        upload.object_asset_id = object_asset.id
        upload.failure_code = None
        upload.updated_at = now
        upload.completed_at = now
        session.flush((upload,))
        return document, revision, relation

    @staticmethod
    def mark_failed(
        upload: UploadSession,
        *,
        failure_code: str,
        now: datetime,
    ) -> None:
        upload.state = UploadSessionState.FAILED.value
        upload.object_asset_id = None
        upload.failure_code = failure_code
        upload.updated_at = now
        upload.completed_at = now

    @staticmethod
    def list_documents(
        session: Session,
        *,
        organization_id: UUID,
        project_id: UUID,
        cursor: UUID | None,
        limit: int,
    ) -> list[DocumentListRow]:
        revision_alias = aliased(DocumentRevision)
        latest_revision_id = (
            select(revision_alias.id)
            .where(revision_alias.document_id == Document.id)
            .order_by(desc(revision_alias.id))
            .limit(1)
            .correlate(Document)
            .scalar_subquery()
        )
        statement = (
            select(Document, Project, DocumentRevision, AccessScope, LicensePolicy)
            .join(
                Project,
                (Project.id == Document.project_id)
                & (Project.organization_id == Document.organization_id),
            )
            .join(DocumentRevision, DocumentRevision.id == latest_revision_id)
            .join(
                AccessScope,
                (AccessScope.id == DocumentRevision.access_scope_id)
                & (AccessScope.organization_id == DocumentRevision.organization_id),
            )
            .join(
                LicensePolicy,
                (LicensePolicy.id == DocumentRevision.license_policy_id)
                & (LicensePolicy.organization_id == DocumentRevision.organization_id)
                & (LicensePolicy.access_scope_id == DocumentRevision.access_scope_id),
            )
            .join(
                DocumentAsset,
                (DocumentAsset.revision_id == DocumentRevision.id)
                & (DocumentAsset.organization_id == DocumentRevision.organization_id)
                & (DocumentAsset.project_id == DocumentRevision.project_id)
                & (DocumentAsset.asset_kind == DocumentAssetKind.ORIGINAL.value),
            )
            .join(
                ObjectAsset,
                (ObjectAsset.id == DocumentAsset.object_asset_id)
                & (ObjectAsset.organization_id == DocumentAsset.organization_id)
                & (ObjectAsset.project_id == DocumentAsset.project_id)
                & (ObjectAsset.access_scope == DocumentRevision.access_scope)
                & (ObjectAsset.access_scope_id == DocumentRevision.access_scope_id)
                & (ObjectAsset.license_policy_id == DocumentRevision.license_policy_id)
                & (ObjectAsset.asset_kind == "DOCUMENT_ORIGINAL")
                & (ObjectAsset.state == ObjectAssetState.AVAILABLE.value),
            )
            .where(
                Document.organization_id == organization_id,
                Document.project_id == project_id,
                LicensePolicy.allow_metadata_read.is_(True),
            )
            .order_by(desc(Document.id))
            .limit(limit)
        )
        if cursor is not None:
            statement = statement.where(Document.id < cursor)
        return [
            DocumentListRow(
                document=row[0],
                project=row[1],
                revision=row[2],
                access_scope=row[3],
                license_policy=row[4],
            )
            for row in session.execute(statement)
        ]

    @staticmethod
    def get_revision(
        session: Session,
        *,
        organization_id: UUID,
        revision_id: UUID,
    ) -> DocumentRevisionRow:
        row = session.execute(
            select(
                Document,
                Project,
                DocumentRevision,
                SourceOrganization,
                AccessScope,
                LicensePolicy,
                DocumentAsset,
                ObjectAsset,
            )
            .join(
                DocumentRevision,
                (DocumentRevision.document_id == Document.id)
                & (DocumentRevision.organization_id == Document.organization_id)
                & (DocumentRevision.project_id == Document.project_id),
            )
            .join(
                Project,
                (Project.id == Document.project_id)
                & (Project.organization_id == Document.organization_id),
            )
            .join(
                SourceOrganization,
                (SourceOrganization.id == DocumentRevision.source_organization_id)
                & (SourceOrganization.organization_id == DocumentRevision.organization_id),
            )
            .join(
                AccessScope,
                (AccessScope.id == DocumentRevision.access_scope_id)
                & (AccessScope.organization_id == DocumentRevision.organization_id),
            )
            .join(
                LicensePolicy,
                (LicensePolicy.id == DocumentRevision.license_policy_id)
                & (LicensePolicy.organization_id == DocumentRevision.organization_id)
                & (LicensePolicy.access_scope_id == DocumentRevision.access_scope_id),
            )
            .join(
                DocumentAsset,
                (DocumentAsset.revision_id == DocumentRevision.id)
                & (DocumentAsset.organization_id == DocumentRevision.organization_id)
                & (DocumentAsset.asset_kind == DocumentAssetKind.ORIGINAL.value),
            )
            .join(
                ObjectAsset,
                (ObjectAsset.id == DocumentAsset.object_asset_id)
                & (ObjectAsset.organization_id == DocumentAsset.organization_id)
                & (ObjectAsset.project_id == DocumentAsset.project_id)
                & (ObjectAsset.access_scope == DocumentRevision.access_scope)
                & (ObjectAsset.access_scope_id == DocumentRevision.access_scope_id)
                & (ObjectAsset.license_policy_id == DocumentRevision.license_policy_id)
                & (ObjectAsset.asset_kind == "DOCUMENT_ORIGINAL")
                & (ObjectAsset.state == ObjectAssetState.AVAILABLE.value),
            )
            .where(
                DocumentRevision.id == revision_id,
                DocumentRevision.organization_id == organization_id,
            )
        ).one_or_none()
        if row is None:
            raise DocumentNotFoundError()
        return DocumentRevisionRow(
            document=row[0],
            project=row[1],
            revision=row[2],
            source_organization=row[3],
            access_scope=row[4],
            license_policy=row[5],
            document_asset=row[6],
            object_asset=row[7],
        )

    @staticmethod
    def upload_scope_statement(
        *,
        organization_id: UUID,
        upload_id: UUID,
    ) -> Select[tuple[UploadSession]]:
        return select(UploadSession).where(
            UploadSession.id == upload_id,
            UploadSession.organization_id == organization_id,
        )


def now_for_update() -> datetime:
    """A small seam retained for deterministic repository tests."""

    return utc_now()
