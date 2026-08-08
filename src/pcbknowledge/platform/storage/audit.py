"""Concrete adapter from object reads to the append-only audit writer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from pcbknowledge.platform.audit import AuditEventDraft, AuditOutcome, AuditWriter
from pcbknowledge.platform.identity.types import Principal
from pcbknowledge.platform.storage.errors import ObjectAuditRequiredError


class AuditWriterAssetReadAuditor:
    """Write successful download-URL issuance without keys, URLs, or credentials."""

    def __init__(self, writer: AuditWriter, principal: Principal) -> None:
        self._writer = writer
        self._principal = principal

    def record_asset_read(
        self,
        session: Session,
        *,
        organization_id: UUID,
        project_id: UUID | None,
        actor_subject_id: UUID,
        asset_id: UUID,
    ) -> UUID:
        if (
            self._principal.organization_id != organization_id
            or self._principal.subject_id != actor_subject_id
        ):
            raise ObjectAuditRequiredError()
        event = self._writer.append(
            session,
            AuditEventDraft(
                organization_id=organization_id,
                project_id=project_id,
                action="object_asset.download_url_issued",
                resource_type="object_asset",
                resource_id=asset_id,
                outcome=AuditOutcome.SUCCEEDED,
                detail={},
            ),
            principal=self._principal,
        )
        return event.id
