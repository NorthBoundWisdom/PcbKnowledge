"""Safe Agent-facing CLI for Git-native typed draft preparation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityKind,
    EntityRecord,
    EvidenceAnchor,
    FactRecord,
    FactType,
    LicenseClass,
    ParameterLimitKind,
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
    normalize_lookup,
)
from pcbknowledge.git_native.store import (
    ChangeScope,
    EvidenceError,
    FactConflict,
    KnowledgeRepository,
    RecordConflictError,
    RecordNotFoundError,
    RepositoryError,
)


SOURCE_EDITABLE_FIELDS = (
    "title",
    "document_number",
    "revision",
    "source_locator",
    "source_publisher",
    "license_note",
    "preparation_note",
    "supersedes",
)


class AgentProcessingBlockedError(RepositoryError):
    """Source policy forbids exposing raw or derived content to an Agent."""


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _repository(root: str) -> KnowledgeRepository:
    repository = KnowledgeRepository(Path(root))
    repository.ensure_layout()
    return repository


def _source_projection(record: SourceRecord) -> dict[str, Any]:
    value = record.to_dict()
    evidence = value["evidence"]
    if not isinstance(evidence, dict):
        raise RecordValidationError("source evidence projection is invalid")

    # A normal Agent read never reveals the stored path.  The only command that
    # returns it is source authorize-read, after the license gate and byte
    # verification have both passed.
    evidence["path"] = None
    evidence["present"] = record.evidence.present
    if not record.evidence.present:
        evidence_access = "NOT_PRESENT"
    elif record.agent_processing_allowed:
        evidence_access = "REQUIRES_AUTHORIZE_READ"
    else:
        evidence_access = "LICENSE_BLOCKED"

    missing = list(record.missing_fields)
    return {
        **value,
        "record_type": "SOURCE",
        "revision_token": record.revision_token,
        "missing_fields": missing,
        "unknown_fields": [item for item in missing if item != "evidence"],
        "missing_evidence": "evidence" in missing,
        "next_actions": list(record.next_actions),
        "agent_processing_allowed": record.agent_processing_allowed,
        "evidence_access": evidence_access,
    }


def _entity_unknown_fields(record: EntityRecord) -> list[str]:
    if record.kind is EntityKind.COMPONENT and record.family is None:
        return ["family"]
    return []


def _entity_projection(record: EntityRecord) -> dict[str, Any]:
    return {
        **record.to_dict(),
        "record_type": "ENTITY",
        "revision_token": record.revision_token,
        "unknown_fields": _entity_unknown_fields(record),
    }


def _fact_unknown_fields(record: FactRecord) -> list[str]:
    payload = record.payload
    if isinstance(payload, ComponentPinPayload):
        return [] if payload.pin_name is not None else ["payload.pin_name"]
    fields: list[str] = []
    for name in ("minimum", "typical", "maximum"):
        if getattr(payload, name) is None:
            fields.append(f"payload.{name}")
    return fields


def _missing_anchors(record: FactRecord) -> list[dict[str, object]]:
    if not record.evidence_anchors:
        return [
            {
                "anchor_index": None,
                "missing_fields": ["evidence_anchor"],
            }
        ]
    missing: list[dict[str, object]] = []
    for index, anchor in enumerate(record.evidence_anchors):
        fields: list[str] = []
        if anchor.bbox is None:
            fields.append("bbox")
        if anchor.quote is None:
            fields.append("quote")
        if fields:
            missing.append(
                {
                    "anchor_index": index,
                    "source_id": anchor.source_id,
                    "page": anchor.page,
                    "missing_fields": fields,
                }
            )
    return missing


def _fact_next_actions(record: FactRecord) -> list[str]:
    if record.status in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
        actions: list[str] = []
        if record.missing_fields:
            actions.append("ADD_COMPLETE_EVIDENCE_ANCHOR")
        actions.extend(("EDIT", "SUBMIT"))
        return actions
    if record.status is RecordStatus.READY_FOR_REVIEW:
        return ["WAIT_FOR_HUMAN_REVIEW"]
    return []


def _fact_projection(
    record: FactRecord, *, conflicting_fact_ids: Sequence[str] = ()
) -> dict[str, Any]:
    return {
        **record.to_dict(),
        "record_type": "FACT",
        "revision_token": record.revision_token,
        "missing_fields": list(record.missing_fields),
        "missing_anchors": _missing_anchors(record),
        "unknown_fields": _fact_unknown_fields(record),
        "conflicting_fact_ids": list(conflicting_fact_ids),
        "next_actions": _fact_next_actions(record),
    }


def _conflict_memberships(
    conflicts: Iterable[FactConflict],
) -> dict[str, tuple[str, ...]]:
    memberships: dict[str, tuple[str, ...]] = {}
    for conflict in conflicts:
        for fact_id in conflict.fact_ids:
            memberships[fact_id] = tuple(
                item for item in conflict.fact_ids if item != fact_id
            )
    return memberships


def _blocked_sources(
    repository: KnowledgeRepository, source_ids: Iterable[str]
) -> list[SourceRecord]:
    blocked: list[SourceRecord] = []
    for source_id in dict.fromkeys(source_ids):
        source = repository.load_source(source_id)
        if not source.agent_processing_allowed:
            blocked.append(source)
    return blocked


def _require_source_processing_allowed(source: SourceRecord) -> None:
    if not source.agent_processing_allowed:
        raise AgentProcessingBlockedError(
            "Agent processing is blocked for source "
            f"{source.id} with license class {source.license_class.value}"
        )


def _require_fact_visible(
    repository: KnowledgeRepository, fact: FactRecord
) -> None:
    blocked = _blocked_sources(repository, fact.source_ids)
    if blocked:
        source = blocked[0]
        raise AgentProcessingBlockedError(
            "Agent access to derived fact content is blocked by source "
            f"{source.id} with license class {source.license_class.value}"
        )


def _require_fact_visible_from_sources(
    fact: FactRecord, sources: Mapping[str, SourceRecord]
) -> None:
    for source_id in fact.source_ids:
        source = sources.get(source_id)
        if source is None:
            raise RecordValidationError(
                f"fact {fact.id} references a missing source in its snapshot"
            )
        if not source.agent_processing_allowed:
            raise AgentProcessingBlockedError(
                "Agent access to derived fact content is blocked by source "
                f"{source.id} with license class {source.license_class.value}"
            )


def _require_anchors_allowed(
    repository: KnowledgeRepository, anchors: Sequence[EvidenceAnchor]
) -> None:
    blocked = _blocked_sources(
        repository, (anchor.source_id for anchor in anchors)
    )
    if blocked:
        source = blocked[0]
        raise AgentProcessingBlockedError(
            "Agent fact preparation is blocked by source "
            f"{source.id} with license class {source.license_class.value}"
        )


# Source commands ------------------------------------------------------


def _source_create(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    record_id = deterministic_record_id(arguments.idempotency_key)
    source_type = arguments.source_type or SourceType.DATASHEET
    requested_license = arguments.license_class
    blank = SourceRecord.new(
        record_id,
        prepared_by=PreparedBy.AGENT,
        source_type=source_type,
    )

    try:
        existing = repository.load_source(record_id)
    except RecordNotFoundError:
        existing = None

    effective_license = (
        requested_license
        if requested_license is not None
        else existing.license_class
        if existing is not None
        else LicenseClass.UNKNOWN
    )
    if arguments.pdf is not None and not effective_license.agent_processing_allowed:
        raise AgentProcessingBlockedError(
            "Agent PDF processing is blocked until an allowed license class is explicit"
        )

    if existing is not None:
        if existing.prepared_by is not PreparedBy.AGENT:
            raise RecordConflictError("idempotency key belongs to a different origin")
        desired_evidence = (
            repository.inspect_pdf_path(Path(arguments.pdf))
            if arguments.pdf is not None
            else existing.evidence
        )
        desired = blank.edit(
            title=existing.title if arguments.title is None else arguments.title,
            document_number=(
                existing.document_number
                if arguments.document_number is None
                else arguments.document_number
            ),
            revision=(
                existing.revision if arguments.revision is None else arguments.revision
            ),
            source_locator=(
                existing.source.locator
                if arguments.source_locator is None
                else arguments.source_locator
            ),
            source_publisher=(
                existing.source.publisher
                if arguments.source_publisher is None
                else arguments.source_publisher
            ),
            license_class=effective_license,
            license_note=(
                existing.license_note
                if arguments.license_note is None
                else arguments.license_note
            ),
            evidence=desired_evidence,
            preparation_note=(
                existing.preparation_note
                if arguments.preparation_note is None
                else arguments.preparation_note
            ),
            supersedes=(
                existing.supersedes
                if arguments.supersedes is None
                else arguments.supersedes
            ),
            source_type=(
                existing.source_type
                if arguments.source_type is None
                else arguments.source_type
            ),
        )
        desired_content = desired.to_dict()
        existing_content = existing.to_dict()
        for field in ("status", "review_history", "review"):
            desired_content.pop(field)
            existing_content.pop(field)
        if desired_content != existing_content:
            raise RecordConflictError(
                "idempotency key already exists with different content; use source update"
            )
        _print({**_source_projection(existing), "replayed": True})
        return 0

    validated = blank.edit(
        title=arguments.title,
        document_number=arguments.document_number,
        revision=arguments.revision,
        source_locator=arguments.source_locator,
        source_publisher=arguments.source_publisher,
        license_class=effective_license,
        license_note=arguments.license_note,
        evidence=blank.evidence,
        preparation_note=arguments.preparation_note,
        supersedes=arguments.supersedes,
        source_type=source_type,
    )
    evidence = (
        repository.import_pdf_path(Path(arguments.pdf))
        if arguments.pdf is not None
        else validated.evidence
    )
    updated = validated.edit(
        title=validated.title,
        document_number=validated.document_number,
        revision=validated.revision,
        source_locator=validated.source.locator,
        source_publisher=validated.source.publisher,
        license_class=validated.license_class,
        license_note=validated.license_note,
        evidence=evidence,
        preparation_note=validated.preparation_note,
        supersedes=validated.supersedes,
        source_type=validated.source_type,
    )
    repository.insert_source(updated)
    _print({**_source_projection(updated), "replayed": False})
    return 0


def _updated_value(
    arguments: argparse.Namespace,
    clear: set[str],
    field: str,
    current: str | None,
) -> str | None:
    if field in clear:
        return None
    supplied = getattr(arguments, field)
    return current if supplied is None else supplied


def _source_update(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    record = repository.load_source(arguments.record_id)
    clear = set(arguments.clear)
    evidence = record.evidence
    if arguments.clear_evidence:
        evidence = type(record.evidence)()
    values = {
        "title": _updated_value(arguments, clear, "title", record.title),
        "document_number": _updated_value(
            arguments, clear, "document_number", record.document_number
        ),
        "revision": _updated_value(arguments, clear, "revision", record.revision),
        "source_locator": _updated_value(
            arguments, clear, "source_locator", record.source.locator
        ),
        "source_publisher": _updated_value(
            arguments, clear, "source_publisher", record.source.publisher
        ),
        "license_class": arguments.license_class or record.license_class,
        "license_note": _updated_value(
            arguments, clear, "license_note", record.license_note
        ),
        "preparation_note": _updated_value(
            arguments, clear, "preparation_note", record.preparation_note
        ),
        "supersedes": _updated_value(
            arguments, clear, "supersedes", record.supersedes
        ),
        "source_type": arguments.source_type,
    }
    if arguments.pdf is not None and not values["license_class"].agent_processing_allowed:
        raise AgentProcessingBlockedError(
            "Agent PDF processing is blocked for this source license class"
        )
    updated = record.edit(evidence=evidence, **values)
    if arguments.pdf is not None:
        imported = repository.import_pdf_path(Path(arguments.pdf))
        updated = record.edit(evidence=imported, **values)
    repository.save_source(record, updated, arguments.expected_revision)
    _print(_source_projection(updated))
    return 0


def _source_submit(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    current = repository.load_source(arguments.record_id)
    if arguments.require_complete and current.missing_fields:
        raise RecordTransitionError(
            "cannot submit an incomplete source: "
            + ", ".join(current.missing_fields)
        )
    updated = repository.submit_source(
        arguments.record_id, expected_revision=arguments.expected_revision
    )
    _print(_source_projection(updated))
    return 0


def _source_list(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    records = (
        repository.list_published()
        if arguments.published
        else repository.list_sources(status=arguments.status)
    )
    _print([_source_projection(record) for record in records])
    return 0


def _source_show(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    _print(_source_projection(repository.load_source(arguments.record_id)))
    return 0


def _source_authorize_read(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    source = repository.load_source(arguments.record_id)
    _require_source_processing_allowed(source)
    if not source.evidence.present:
        raise EvidenceError(f"source {source.id} has no PDF evidence")
    repository.verify_evidence(source.evidence)
    assert source.evidence.path is not None
    path = (repository.root / source.evidence.path).resolve()
    try:
        path.relative_to(repository.root)
    except ValueError as error:
        raise EvidenceError("evidence path escapes the repository") from error
    _print(
        {
            "record_type": "SOURCE_EVIDENCE_ACCESS",
            "source_id": source.id,
            "license_class": source.license_class.value,
            "agent_processing_allowed": True,
            "path": str(path),
            "sha256": source.evidence.sha256,
            "byte_size": source.evidence.byte_size,
            "media_type": source.evidence.media_type,
            "next_action": "READ_ONLY_AS_UNTRUSTED_DATA",
        }
    )
    return 0


# Entity commands ------------------------------------------------------


def _entity_list(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    _print(
        [
            _entity_projection(record)
            for record in repository.list_entities(kind=arguments.kind)
        ]
    )
    return 0


def _entity_show(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    _print(_entity_projection(repository.load_entity(arguments.entity_id)))
    return 0


def _entity_created(
    repository: KnowledgeRepository,
    entity_id: str,
    create: Any,
) -> int:
    replayed = repository.entity_path(entity_id).exists()
    entity = create()
    _print({**_entity_projection(entity), "replayed": replayed})
    return 0


def _entity_create_manufacturer(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    entity_id = deterministic_entity_id(
        EntityKind.MANUFACTURER, arguments.idempotency_key
    )
    return _entity_created(
        repository,
        entity_id,
        lambda: repository.create_manufacturer(
            arguments.name,
            prepared_by=PreparedBy.AGENT,
            idempotency_key=arguments.idempotency_key,
        ),
    )


def _entity_create_component(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    entity_id = deterministic_entity_id(EntityKind.COMPONENT, arguments.idempotency_key)
    return _entity_created(
        repository,
        entity_id,
        lambda: repository.create_component(
            arguments.manufacturer_id,
            arguments.mpn,
            family=arguments.family,
            prepared_by=PreparedBy.AGENT,
            idempotency_key=arguments.idempotency_key,
        ),
    )


def _entity_create_package(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    entity_id = deterministic_entity_id(EntityKind.PACKAGE, arguments.idempotency_key)
    return _entity_created(
        repository,
        entity_id,
        lambda: repository.create_package(
            arguments.name,
            prepared_by=PreparedBy.AGENT,
            idempotency_key=arguments.idempotency_key,
        ),
    )


def _resolution(
    *, query: dict[str, object], matches: Sequence[EntityRecord]
) -> int:
    if not matches:
        result = "UNKNOWN"
        next_action = "KEEP_UNKNOWN_OR_CREATE_ONLY_FROM_VERIFIED_IDENTITY"
    elif len(matches) == 1:
        result = "EXACT"
        next_action = "USE_EXACT_ENTITY_ID"
    else:
        result = "CONFLICT"
        next_action = "STOP_AND_RESOLVE_CONFLICT"
    _print(
        {
            "record_type": "ENTITY_RESOLUTION",
            "result": result,
            "query": query,
            "matches": [_entity_projection(item) for item in matches],
            "unknown": result == "UNKNOWN",
            "conflict": result == "CONFLICT",
            "next_action": next_action,
        }
    )
    return 2 if result == "CONFLICT" else 0


def _entity_resolve_manufacturer(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    return _resolution(
        query={
            "kind": EntityKind.MANUFACTURER.value,
            "raw_name": arguments.name,
            "normalized_key": normalize_lookup(arguments.name),
        },
        matches=repository.find_manufacturers_exact(arguments.name),
    )


def _entity_resolve_component(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    try:
        manufacturer = repository.load_entity(arguments.manufacturer_id)
    except RecordNotFoundError:
        manufacturer = None
    if manufacturer is None or manufacturer.kind is not EntityKind.MANUFACTURER:
        matches: Sequence[EntityRecord] = ()
        reason = "MANUFACTURER_UNKNOWN"
    else:
        matches = repository.find_components_exact(
            arguments.manufacturer_id, arguments.mpn
        )
        reason = None
    query: dict[str, object] = {
        "kind": EntityKind.COMPONENT.value,
        "manufacturer_id": arguments.manufacturer_id,
        "raw_mpn": arguments.mpn,
        "normalized_mpn": normalize_lookup(arguments.mpn),
    }
    if reason is not None:
        query["reason"] = reason
    return _resolution(query=query, matches=matches)


def _entity_resolve_package(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    return _resolution(
        query={
            "kind": EntityKind.PACKAGE.value,
            "raw_name": arguments.name,
            "normalized_key": normalize_lookup(arguments.name),
        },
        matches=repository.find_packages_exact(arguments.name),
    )


# Fact commands --------------------------------------------------------


def _parse_anchors(arguments: argparse.Namespace) -> tuple[EvidenceAnchor, ...]:
    complete = getattr(arguments, "anchor", None) or []
    page_only = getattr(arguments, "page_anchor", None) or []
    anchors: list[EvidenceAnchor] = []
    for source_id, raw_page, raw_x0, raw_y0, raw_x1, raw_y1, quote in complete:
        try:
            page = int(raw_page)
            bbox = (
                float(raw_x0),
                float(raw_y0),
                float(raw_x1),
                float(raw_y1),
            )
        except ValueError as error:
            raise RecordValidationError(
                "--anchor requires integer PAGE and numeric normalized bbox values"
            ) from error
        anchors.append(EvidenceAnchor.create(source_id, page, bbox=bbox, quote=quote))
    for source_id, raw_page in page_only:
        try:
            page = int(raw_page)
        except ValueError as error:
            raise RecordValidationError(
                "--page-anchor requires an integer PAGE"
            ) from error
        anchors.append(EvidenceAnchor.create(source_id, page))
    return tuple(anchors)


def _anchors_for_update(
    arguments: argparse.Namespace, current: tuple[EvidenceAnchor, ...]
) -> tuple[EvidenceAnchor, ...]:
    supplied = arguments.anchor is not None or arguments.page_anchor is not None
    if arguments.clear_anchors and supplied:
        raise RecordValidationError(
            "--clear-anchors cannot be combined with --anchor or --page-anchor"
        )
    if arguments.clear_anchors:
        return ()
    return _parse_anchors(arguments) if supplied else current


def _fact_conflict_map(repository: KnowledgeRepository) -> dict[str, tuple[str, ...]]:
    return _conflict_memberships(repository.fact_conflicts())


def _create_or_replay_fact(
    repository: KnowledgeRepository,
    *,
    idempotency_key: str,
    fact_type: FactType,
    payload: ComponentPinPayload | ParameterLimitPayload,
    conditions: tuple[str, ...],
    applicability: tuple[str, ...],
    anchors: tuple[EvidenceAnchor, ...],
    supersedes: str | None,
) -> tuple[FactRecord, bool]:
    fact_id = deterministic_fact_id(idempotency_key)
    desired = FactRecord.new(
        fact_id,
        fact_type=fact_type,
        payload=payload,
        prepared_by=PreparedBy.AGENT,
        conditions=conditions,
        applicability=applicability,
        evidence_anchors=anchors,
        supersedes=supersedes,
    )
    if repository.fact_path(fact_id).exists():
        current = repository.load_fact(fact_id)
        _require_fact_visible(repository, current)
        if current.prepared_by is not PreparedBy.AGENT:
            raise RecordConflictError(
                "fact idempotency key belongs to a different origin"
            )
        desired_content = desired.to_dict()
        current_content = current.to_dict()
        for field in ("status", "review_history", "review"):
            desired_content.pop(field)
            current_content.pop(field)
        if desired_content != current_content:
            raise RecordConflictError(
                "fact idempotency key exists with different content; use fact update"
            )
        return current, True

    created = repository.create_fact(
        idempotency_key=idempotency_key,
        fact_type=fact_type,
        payload=payload,
        prepared_by=PreparedBy.AGENT,
        conditions=conditions,
        applicability=applicability,
        evidence_anchors=anchors,
        supersedes=supersedes,
    )
    return created, False


def _fact_list(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    if arguments.published:
        snapshot = repository.read_published_snapshot()
        records = list(snapshot.facts)
        conflicts = snapshot.conflicts
        published_sources = {source.id: source for source in snapshot.sources}
    else:
        records = repository.list_facts(status=arguments.status)
        conflicts = repository.fact_conflicts()
        published_sources = None
    if arguments.fact_type is not None:
        records = [item for item in records if item.fact_type is arguments.fact_type]
    for fact in records:
        if published_sources is None:
            _require_fact_visible(repository, fact)
        else:
            _require_fact_visible_from_sources(fact, published_sources)
    memberships = _conflict_memberships(conflicts)
    _print(
        [
            _fact_projection(
                fact, conflicting_fact_ids=memberships.get(fact.id, ())
            )
            for fact in records
        ]
    )
    return 0


def _fact_show(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    fact = repository.load_fact(arguments.fact_id)
    _require_fact_visible(repository, fact)
    _print(
        _fact_projection(
            fact,
            conflicting_fact_ids=_fact_conflict_map(repository).get(fact.id, ()),
        )
    )
    return 0


def _fact_conflicts(repository: KnowledgeRepository, _arguments: argparse.Namespace) -> int:
    conflicts = repository.fact_conflicts()
    for conflict in conflicts:
        for fact_id in conflict.fact_ids:
            _require_fact_visible(repository, repository.load_fact(fact_id))
    _print(
        {
            "record_type": "FACT_CONFLICTS",
            "count": len(conflicts),
            "conflicts": [
                {
                    "semantic_key": list(conflict.semantic_key),
                    "fact_ids": list(conflict.fact_ids),
                    "next_action": "RESOLVE_OR_SUPERSEDE_BEFORE_APPROVAL",
                }
                for conflict in conflicts
            ],
        }
    )
    return 2 if conflicts else 0


def _fact_create_pin(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    anchors = _parse_anchors(arguments)
    _require_anchors_allowed(repository, anchors)
    fact, replayed = _create_or_replay_fact(
        repository,
        idempotency_key=arguments.idempotency_key,
        fact_type=FactType.COMPONENT_PIN,
        payload=ComponentPinPayload(
            arguments.component_id,
            arguments.package_id,
            arguments.pin_number,
            arguments.pin_name,
            arguments.primary_function,
            tuple(arguments.alternate_function),
        ),
        conditions=tuple(arguments.condition),
        applicability=tuple(arguments.applicability),
        anchors=anchors,
        supersedes=arguments.supersedes,
    )
    _print(
        {
            **_fact_projection(
                fact,
                conflicting_fact_ids=_fact_conflict_map(repository).get(fact.id, ()),
            ),
            "replayed": replayed,
        }
    )
    return 0


def _fact_create_parameter(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    anchors = _parse_anchors(arguments)
    _require_anchors_allowed(repository, anchors)
    fact, replayed = _create_or_replay_fact(
        repository,
        idempotency_key=arguments.idempotency_key,
        fact_type=FactType.PARAMETER_LIMIT,
        payload=ParameterLimitPayload(
            arguments.component_id,
            arguments.parameter,
            arguments.limit_kind,
            arguments.minimum,
            arguments.typical,
            arguments.maximum,
            arguments.unit,
        ),
        conditions=tuple(arguments.condition),
        applicability=tuple(arguments.applicability),
        anchors=anchors,
        supersedes=arguments.supersedes,
    )
    _print(
        {
            **_fact_projection(
                fact,
                conflicting_fact_ids=_fact_conflict_map(repository).get(fact.id, ()),
            ),
            "replayed": replayed,
        }
    )
    return 0


def _fact_edit_common(
    record: FactRecord,
    arguments: argparse.Namespace,
    *,
    payload: ComponentPinPayload | ParameterLimitPayload,
) -> FactRecord:
    anchors = _anchors_for_update(arguments, record.evidence_anchors)
    if arguments.clear_conditions:
        conditions = ()
    else:
        conditions = (
            record.conditions
            if arguments.condition is None
            else tuple(arguments.condition)
        )
    if arguments.clear_applicability:
        applicability = ()
    else:
        applicability = (
            record.applicability
            if arguments.applicability is None
            else tuple(arguments.applicability)
        )
    values: dict[str, Any] = {
        "payload": payload,
        "conditions": conditions,
        "applicability": applicability,
        "evidence_anchors": anchors,
    }
    if arguments.clear_supersedes:
        values["supersedes"] = None
    elif arguments.supersedes is not None:
        values["supersedes"] = arguments.supersedes
    return record.edit(**values)


def _fact_update_pin(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    record = repository.load_fact(arguments.fact_id)
    _require_fact_visible(repository, record)
    if not isinstance(record.payload, ComponentPinPayload):
        raise RecordValidationError("fact is not a COMPONENT_PIN fact")
    current = record.payload
    if arguments.clear_pin_name:
        pin_name = None
    else:
        pin_name = current.pin_name if arguments.pin_name is None else arguments.pin_name
    payload = ComponentPinPayload(
        current.component_id
        if arguments.component_id is None
        else arguments.component_id,
        current.package_id if arguments.package_id is None else arguments.package_id,
        current.pin_number if arguments.pin_number is None else arguments.pin_number,
        pin_name,
        current.primary_function
        if arguments.primary_function is None
        else arguments.primary_function,
        ()
        if arguments.clear_alternate_functions
        else current.alternate_functions
        if arguments.alternate_function is None
        else tuple(arguments.alternate_function),
    )
    updated = _fact_edit_common(record, arguments, payload=payload)
    _require_anchors_allowed(repository, updated.evidence_anchors)
    repository.save_fact(record, updated, arguments.expected_revision)
    _print(
        _fact_projection(
            updated,
            conflicting_fact_ids=_fact_conflict_map(repository).get(updated.id, ()),
        )
    )
    return 0


def _updated_number(
    supplied: float | None, clear: bool, current: float | int | None
) -> float | int | None:
    if clear:
        return None
    return current if supplied is None else supplied


def _fact_update_parameter(
    repository: KnowledgeRepository, arguments: argparse.Namespace
) -> int:
    record = repository.load_fact(arguments.fact_id)
    _require_fact_visible(repository, record)
    if not isinstance(record.payload, ParameterLimitPayload):
        raise RecordValidationError("fact is not a PARAMETER_LIMIT fact")
    current = record.payload
    payload = ParameterLimitPayload(
        current.component_id
        if arguments.component_id is None
        else arguments.component_id,
        current.parameter if arguments.parameter is None else arguments.parameter,
        current.limit_kind
        if arguments.limit_kind is None
        else arguments.limit_kind,
        _updated_number(arguments.minimum, arguments.clear_minimum, current.minimum),
        _updated_number(arguments.typical, arguments.clear_typical, current.typical),
        _updated_number(arguments.maximum, arguments.clear_maximum, current.maximum),
        current.unit if arguments.unit is None else arguments.unit,
    )
    updated = _fact_edit_common(record, arguments, payload=payload)
    _require_anchors_allowed(repository, updated.evidence_anchors)
    repository.save_fact(record, updated, arguments.expected_revision)
    _print(
        _fact_projection(
            updated,
            conflicting_fact_ids=_fact_conflict_map(repository).get(updated.id, ()),
        )
    )
    return 0


def _fact_submit(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    current = repository.load_fact(arguments.fact_id)
    _require_fact_visible(repository, current)
    if current.missing_fields:
        raise RecordTransitionError(
            "cannot submit an incomplete fact: " + ", ".join(current.missing_fields)
        )
    updated = repository.submit_fact(
        current.id, expected_revision=arguments.expected_revision
    )
    _print(
        _fact_projection(
            updated,
            conflicting_fact_ids=_fact_conflict_map(repository).get(updated.id, ()),
        )
    )
    return 0


# Repository/report commands -----------------------------------------


def _validate(repository: KnowledgeRepository, _arguments: argparse.Namespace) -> int:
    snapshot = repository.validate_all(require_canonical=True)
    published = repository.read_published_snapshot()
    _print(
        {
            "status": "VALID",
            "sources": len(snapshot.sources),
            "entities": len(snapshot.entities),
            "facts": len(snapshot.facts),
            "conflicts": len(snapshot.conflicts),
            "published_sources": len(published.sources),
            "published_facts": len(published.facts),
        }
    )
    return 0


def _require_diff_visible(repository: KnowledgeRepository) -> None:
    for relative in repository.git_candidate_paths():
        if not relative.startswith(("knowledge/", "evidence/")):
            continue
        path = repository.root / relative
        if relative.startswith(("knowledge/sources/", "knowledge/facts/")):
            if not path.exists():
                raise AgentProcessingBlockedError(
                    "Agent diff cannot expose deleted Source/Fact authority"
                )
        if relative.startswith("knowledge/sources/") and path.suffix == ".json":
            source = repository.load_source(path.stem)
            _require_source_processing_allowed(source)
        elif relative.startswith("knowledge/facts/") and path.suffix == ".json":
            fact = repository.load_fact(path.stem)
            _require_fact_visible(repository, fact)
        elif relative.startswith("evidence/"):
            owners = [
                source
                for source in repository.list_sources()
                if source.evidence.path == relative
            ]
            for source in owners:
                _require_source_processing_allowed(source)


def _diff(repository: KnowledgeRepository, _arguments: argparse.Namespace) -> int:
    _require_diff_visible(repository)
    repository.validate_all(require_canonical=True)
    changes = repository.git_changes()
    print("\n".join(changes.status_lines))
    if changes.tracked_diff:
        print(changes.tracked_diff, end="")
    if changes.untracked_preview:
        print(changes.untracked_preview, end="")
    return 0


def _change_scope(repository: KnowledgeRepository, _arguments: argparse.Namespace) -> int:
    scope = repository.git_change_scope()
    _print(
        {
            "scope": scope.value,
            "valid_for_single_commit": scope is not ChangeScope.MIXED,
            "rule": "knowledge/evidence data and software/policy changes must be separate commits",
        }
    )
    return 2 if scope is ChangeScope.MIXED else 0


def _review_status(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    snapshot = repository.validate_all(require_canonical=True)
    sources = {record.id: record for record in snapshot.sources}
    entities = {record.id: record for record in snapshot.entities}
    facts = {record.id: record for record in snapshot.facts}

    selected_source_ids = set(arguments.source_id)
    selected_entity_ids = set(arguments.entity_id)
    selected_fact_ids = set(arguments.fact_id)
    explicit = bool(selected_source_ids or selected_entity_ids or selected_fact_ids)
    candidate_paths = repository.git_candidate_paths()

    if not explicit:
        for relative in candidate_paths:
            path = Path(relative)
            if len(path.parts) != 3 or path.suffix != ".json":
                continue
            if path.parts[:2] == ("knowledge", "sources"):
                selected_source_ids.add(path.stem)
            elif path.parts[:2] == ("knowledge", "entities"):
                selected_entity_ids.add(path.stem)
            elif path.parts[:2] == ("knowledge", "facts"):
                selected_fact_ids.add(path.stem)

    def require(record_id: str, records: dict[str, Any], label: str) -> Any:
        record = records.get(record_id)
        if record is None:
            raise RecordNotFoundError(f"selected {label} not found: {record_id}")
        return record

    for fact_id in tuple(selected_fact_ids):
        fact = require(fact_id, facts, "fact")
        selected_source_ids.update(fact.source_ids)
        selected_entity_ids.update(fact.subject_entity_ids)
    for entity_id in tuple(selected_entity_ids):
        entity = require(entity_id, entities, "entity")
        if entity.kind is EntityKind.COMPONENT and entity.manufacturer_id is not None:
            selected_entity_ids.add(entity.manufacturer_id)

    selected_sources = [
        require(item, sources, "source") for item in sorted(selected_source_ids)
    ]
    selected_entities = [
        require(item, entities, "entity") for item in sorted(selected_entity_ids)
    ]
    selected_facts = [
        require(item, facts, "fact") for item in sorted(selected_fact_ids)
    ]

    selected_authority_paths = {
        *(f"knowledge/sources/{item.id}.json" for item in selected_sources),
        *(f"knowledge/entities/{item.id}.json" for item in selected_entities),
        *(f"knowledge/facts/{item.id}.json" for item in selected_facts),
    }
    changed_authority_paths = {
        relative
        for relative in candidate_paths
        if relative.startswith(
            ("knowledge/sources/", "knowledge/entities/", "knowledge/facts/")
        )
        and relative.endswith(".json")
    }
    unselected_changes = sorted(changed_authority_paths - selected_authority_paths)

    unknown: list[dict[str, object]] = []
    blocking_unknown: list[dict[str, object]] = []
    for source in selected_sources:
        if source.missing_fields:
            issue = {
                "record_type": "SOURCE",
                "record_id": source.id,
                "fields": list(source.missing_fields),
            }
            unknown.append(issue)
            blocking_unknown.append(issue)
    for entity in selected_entities:
        fields = _entity_unknown_fields(entity)
        if fields:
            unknown.append(
                {
                    "record_type": "ENTITY",
                    "record_id": entity.id,
                    "fields": fields,
                }
            )
    for fact in selected_facts:
        fields = _fact_unknown_fields(fact)
        if fields:
            unknown.append(
                {
                    "record_type": "FACT",
                    "record_id": fact.id,
                    "fields": fields,
                }
            )

    missing_anchors = [
        {"fact_id": fact.id, "anchors": _missing_anchors(fact)}
        for fact in selected_facts
        if fact.missing_fields
    ]

    fact_ids_by_source: dict[str, list[str]] = {}
    for fact in selected_facts:
        for source_id in fact.source_ids:
            fact_ids_by_source.setdefault(source_id, []).append(fact.id)
    license_blocked = [
        {
            "source_id": source.id,
            "license_class": source.license_class.value,
            "fact_ids": sorted(fact_ids_by_source.get(source.id, [])),
        }
        for source in selected_sources
        if not source.agent_processing_allowed
    ]

    relevant_conflicts = [
        conflict
        for conflict in snapshot.conflicts
        if selected_fact_ids.intersection(conflict.fact_ids)
    ]
    blocked_fact_ids = {
        fact_id
        for item in license_blocked
        for fact_id in item["fact_ids"]
        if isinstance(fact_id, str)
    }
    conflict_output = [
        {
            "semantic_key": (
                "REDACTED_LICENSE_BLOCKED"
                if blocked_fact_ids.intersection(conflict.fact_ids)
                else list(conflict.semantic_key)
            ),
            "fact_ids": list(conflict.fact_ids),
        }
        for conflict in relevant_conflicts
    ]

    not_ready = [
        {
            "record_type": "SOURCE",
            "record_id": source.id,
            "status": source.status.value,
        }
        for source in selected_sources
        if source.status not in {RecordStatus.READY_FOR_REVIEW, RecordStatus.APPROVED}
    ]
    not_ready.extend(
        {
            "record_type": "FACT",
            "record_id": fact.id,
            "status": fact.status.value,
        }
        for fact in selected_facts
        if fact.status not in {RecordStatus.READY_FOR_REVIEW, RecordStatus.APPROVED}
    )

    scope = repository.git_change_scope()
    change_count = len(
        [
            relative
            for relative in candidate_paths
            if relative.startswith(("knowledge/", "evidence/"))
        ]
    )
    has_selection = bool(selected_sources or selected_entities or selected_facts)
    review_ready = (
        has_selection
        and scope is ChangeScope.DATA_ONLY
        and change_count > 0
        and not blocking_unknown
        and not missing_anchors
        and not license_blocked
        and not relevant_conflicts
        and not not_ready
        and not unselected_changes
    )
    if scope is ChangeScope.MIXED:
        next_action = "SPLIT_CODE_AND_DATA_CHANGES"
    elif license_blocked:
        next_action = "STOP_LICENSE_BLOCKED"
    elif relevant_conflicts:
        next_action = "RESOLVE_CONFLICT"
    elif blocking_unknown or missing_anchors:
        next_action = "RESOLVE_UNKNOWN_OR_MISSING_ANCHOR"
    elif not_ready:
        next_action = "SUBMIT_SOURCE_AND_FACT_DRAFTS"
    elif unselected_changes:
        next_action = "INCLUDE_OR_SEPARATE_UNSELECTED_DATA_CHANGES"
    elif review_ready:
        next_action = "WAIT_FOR_HUMAN_REVIEW"
    else:
        next_action = "CREATE_DATA_ONLY_DIFF"

    _print(
        {
            "record_type": "KNOWLEDGE_REVIEW_STATUS",
            "review_ready": review_ready,
            "selected": {
                "source_ids": [item.id for item in selected_sources],
                "entity_ids": [item.id for item in selected_entities],
                "fact_ids": [item.id for item in selected_facts],
            },
            "unknown": unknown,
            "missing_anchors": missing_anchors,
            "license_blocked": license_blocked,
            "conflicts": conflict_output,
            "not_ready": not_ready,
            "unselected_changes": unselected_changes,
            "change_scope": scope.value,
            "change_count": change_count,
            "next_action": next_action,
            "human_boundary": "Agent must not approve, reject, stage, commit, or push",
        }
    )
    return 0 if review_ready else 2


# Argument parser ------------------------------------------------------


def _add_source_edit_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title")
    parser.add_argument("--document-number")
    parser.add_argument("--revision")
    parser.add_argument("--source-locator")
    parser.add_argument("--source-publisher")
    parser.add_argument("--license-class", type=LicenseClass, choices=tuple(LicenseClass))
    parser.add_argument("--license-note")
    parser.add_argument("--preparation-note")
    parser.add_argument("--supersedes")
    parser.add_argument("--pdf")
    parser.add_argument("--source-type", type=SourceType, choices=tuple(SourceType))


def _add_source_commands(subparsers: Any) -> None:
    source_parser = subparsers.add_parser(
        "source", help="typed SourceRecord draft commands"
    )
    actions = source_parser.add_subparsers(dest="source_command", required=True)

    list_parser = actions.add_parser("list")
    list_mode = list_parser.add_mutually_exclusive_group()
    list_mode.add_argument("--status", type=RecordStatus, choices=tuple(RecordStatus))
    list_mode.add_argument("--published", action="store_true")
    list_parser.set_defaults(handler=_source_list, published=False, status=None)

    show_parser = actions.add_parser("show")
    show_parser.add_argument("record_id")
    show_parser.set_defaults(handler=_source_show)

    create_parser = actions.add_parser("create")
    create_parser.add_argument("--idempotency-key", required=True)
    _add_source_edit_arguments(create_parser)
    create_parser.set_defaults(
        handler=_source_create, license_class=None, source_type=None
    )

    update_parser = actions.add_parser("update")
    update_parser.add_argument("record_id")
    update_parser.add_argument("--expected-revision", required=True)
    _add_source_edit_arguments(update_parser)
    update_parser.add_argument(
        "--clear", action="append", choices=SOURCE_EDITABLE_FIELDS, default=[]
    )
    update_parser.add_argument("--clear-evidence", action="store_true")
    update_parser.set_defaults(handler=_source_update)

    submit_parser = actions.add_parser("submit")
    submit_parser.add_argument("record_id")
    submit_parser.add_argument("--expected-revision", required=True)
    submit_parser.set_defaults(handler=_source_submit, require_complete=True)

    authorize_parser = actions.add_parser(
        "authorize-read",
        help="apply the license gate, verify bytes, then return the PDF path",
    )
    authorize_parser.add_argument("record_id")
    authorize_parser.set_defaults(handler=_source_authorize_read)


def _add_entity_commands(subparsers: Any) -> None:
    entity_parser = subparsers.add_parser(
        "entity", help="typed exact EntityRecord commands"
    )
    actions = entity_parser.add_subparsers(dest="entity_command", required=True)

    list_parser = actions.add_parser("list")
    list_parser.add_argument("--kind", type=EntityKind, choices=tuple(EntityKind))
    list_parser.set_defaults(handler=_entity_list)

    show_parser = actions.add_parser("show")
    show_parser.add_argument("entity_id")
    show_parser.set_defaults(handler=_entity_show)

    create_manufacturer = actions.add_parser("create-manufacturer")
    create_manufacturer.add_argument("--idempotency-key", required=True)
    create_manufacturer.add_argument("--name", required=True)
    create_manufacturer.set_defaults(handler=_entity_create_manufacturer)

    create_component = actions.add_parser("create-component")
    create_component.add_argument("--idempotency-key", required=True)
    create_component.add_argument("--manufacturer-id", required=True)
    create_component.add_argument("--mpn", required=True)
    create_component.add_argument("--family")
    create_component.set_defaults(handler=_entity_create_component)

    create_package = actions.add_parser("create-package")
    create_package.add_argument("--idempotency-key", required=True)
    create_package.add_argument("--name", required=True)
    create_package.set_defaults(handler=_entity_create_package)

    resolve_manufacturer = actions.add_parser("resolve-manufacturer")
    resolve_manufacturer.add_argument("--name", required=True)
    resolve_manufacturer.set_defaults(handler=_entity_resolve_manufacturer)

    resolve_component = actions.add_parser("resolve-component")
    resolve_component.add_argument("--manufacturer-id", required=True)
    resolve_component.add_argument("--mpn", required=True)
    resolve_component.set_defaults(handler=_entity_resolve_component)

    resolve_package = actions.add_parser("resolve-package")
    resolve_package.add_argument("--name", required=True)
    resolve_package.set_defaults(handler=_entity_resolve_package)


def _add_anchor_arguments(parser: argparse.ArgumentParser, *, update: bool) -> None:
    default: object = None if update else []
    parser.add_argument(
        "--anchor",
        action="append",
        nargs=7,
        default=default,
        metavar=("SOURCE_ID", "PAGE", "X0", "Y0", "X1", "Y1", "QUOTE"),
        help="repeatable complete PDF_NORMALIZED_V1 evidence anchor",
    )
    parser.add_argument(
        "--page-anchor",
        action="append",
        nargs=2,
        default=default,
        metavar=("SOURCE_ID", "PAGE"),
        help="repeatable explicitly incomplete page-only anchor",
    )
    if update:
        parser.add_argument("--clear-anchors", action="store_true")


def _add_fact_context_arguments(
    parser: argparse.ArgumentParser, *, update: bool
) -> None:
    default: object = None if update else []
    if update:
        conditions = parser.add_mutually_exclusive_group()
        conditions.add_argument("--condition", action="append", default=default)
        conditions.add_argument("--clear-conditions", action="store_true")
        applicability = parser.add_mutually_exclusive_group()
        applicability.add_argument(
            "--applicability", action="append", default=default
        )
        applicability.add_argument("--clear-applicability", action="store_true")
    else:
        parser.add_argument("--condition", action="append", default=default)
        parser.add_argument("--applicability", action="append", default=default)
    _add_anchor_arguments(parser, update=update)
    supersedes = parser.add_mutually_exclusive_group()
    supersedes.add_argument("--supersedes")
    if update:
        supersedes.add_argument("--clear-supersedes", action="store_true")


def _add_fact_commands(subparsers: Any) -> None:
    fact_parser = subparsers.add_parser("fact", help="typed FactRecord draft commands")
    actions = fact_parser.add_subparsers(dest="fact_command", required=True)

    list_parser = actions.add_parser("list")
    list_mode = list_parser.add_mutually_exclusive_group()
    list_mode.add_argument("--status", type=RecordStatus, choices=tuple(RecordStatus))
    list_mode.add_argument("--published", action="store_true")
    list_parser.add_argument("--fact-type", type=FactType, choices=tuple(FactType))
    list_parser.set_defaults(handler=_fact_list, published=False, status=None)

    show_parser = actions.add_parser("show")
    show_parser.add_argument("fact_id")
    show_parser.set_defaults(handler=_fact_show)

    conflicts_parser = actions.add_parser("conflicts")
    conflicts_parser.set_defaults(handler=_fact_conflicts)

    create_pin = actions.add_parser("create-pin")
    create_pin.add_argument("--idempotency-key", required=True)
    create_pin.add_argument("--component-id", required=True)
    create_pin.add_argument("--package-id", required=True)
    create_pin.add_argument("--pin-number", required=True)
    create_pin.add_argument("--pin-name")
    create_pin.add_argument("--primary-function", required=True)
    create_pin.add_argument("--alternate-function", action="append", default=[])
    _add_fact_context_arguments(create_pin, update=False)
    create_pin.set_defaults(handler=_fact_create_pin)

    update_pin = actions.add_parser("update-pin")
    update_pin.add_argument("fact_id")
    update_pin.add_argument("--expected-revision", required=True)
    update_pin.add_argument("--component-id")
    update_pin.add_argument("--package-id")
    update_pin.add_argument("--pin-number")
    pin_name = update_pin.add_mutually_exclusive_group()
    pin_name.add_argument("--pin-name")
    pin_name.add_argument("--clear-pin-name", action="store_true")
    update_pin.add_argument("--primary-function")
    alternate = update_pin.add_mutually_exclusive_group()
    alternate.add_argument("--alternate-function", action="append")
    alternate.add_argument("--clear-alternate-functions", action="store_true")
    _add_fact_context_arguments(update_pin, update=True)
    update_pin.set_defaults(handler=_fact_update_pin)

    create_parameter = actions.add_parser("create-parameter")
    create_parameter.add_argument("--idempotency-key", required=True)
    create_parameter.add_argument("--component-id", required=True)
    create_parameter.add_argument("--parameter", required=True)
    create_parameter.add_argument(
        "--limit-kind", type=ParameterLimitKind, choices=tuple(ParameterLimitKind), required=True
    )
    create_parameter.add_argument("--minimum", type=float)
    create_parameter.add_argument("--typical", type=float)
    create_parameter.add_argument("--maximum", type=float)
    create_parameter.add_argument("--unit", required=True)
    _add_fact_context_arguments(create_parameter, update=False)
    create_parameter.set_defaults(handler=_fact_create_parameter)

    update_parameter = actions.add_parser("update-parameter")
    update_parameter.add_argument("fact_id")
    update_parameter.add_argument("--expected-revision", required=True)
    update_parameter.add_argument("--component-id")
    update_parameter.add_argument("--parameter")
    update_parameter.add_argument(
        "--limit-kind", type=ParameterLimitKind, choices=tuple(ParameterLimitKind)
    )
    for name in ("minimum", "typical", "maximum"):
        group = update_parameter.add_mutually_exclusive_group()
        group.add_argument(f"--{name}", type=float)
        group.add_argument(f"--clear-{name}", action="store_true")
    update_parameter.add_argument("--unit")
    _add_fact_context_arguments(update_parameter, update=True)
    update_parameter.set_defaults(handler=_fact_update_parameter)

    submit_parser = actions.add_parser("submit")
    submit_parser.add_argument("fact_id")
    submit_parser.add_argument("--expected-revision", required=True)
    submit_parser.set_defaults(handler=_fact_submit)


def _add_legacy_source_commands(subparsers: Any) -> None:
    """Keep the P0.0 Source-only CLI stable while typed callers migrate."""

    list_parser = subparsers.add_parser("list")
    list_mode = list_parser.add_mutually_exclusive_group()
    list_mode.add_argument("--status", type=RecordStatus, choices=tuple(RecordStatus))
    list_mode.add_argument("--published", action="store_true")
    list_parser.set_defaults(handler=_source_list, published=False, status=None)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("record_id")
    show_parser.set_defaults(handler=_source_show)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--idempotency-key", required=True)
    _add_source_edit_arguments(create_parser)
    create_parser.set_defaults(
        handler=_source_create, license_class=None, source_type=None
    )

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("record_id")
    update_parser.add_argument("--expected-revision", required=True)
    _add_source_edit_arguments(update_parser)
    update_parser.add_argument(
        "--clear", action="append", choices=SOURCE_EDITABLE_FIELDS, default=[]
    )
    update_parser.add_argument("--clear-evidence", action="store_true")
    update_parser.set_defaults(handler=_source_update)

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("record_id")
    submit_parser.add_argument("--expected-revision", required=True)
    submit_parser.set_defaults(handler=_source_submit, require_complete=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Git-native typed PcbKnowledge drafts"
    )
    parser.add_argument(
        "--repo", default=".", help="repository root (default: current directory)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_source_commands(subparsers)
    _add_entity_commands(subparsers)
    _add_fact_commands(subparsers)
    _add_legacy_source_commands(subparsers)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.set_defaults(handler=_validate)

    diff_parser = subparsers.add_parser("diff")
    diff_parser.set_defaults(handler=_diff)

    scope_parser = subparsers.add_parser("change-scope")
    scope_parser.set_defaults(handler=_change_scope)

    review_parser = subparsers.add_parser("review-status")
    review_parser.add_argument("--source-id", action="append", default=[])
    review_parser.add_argument("--entity-id", action="append", default=[])
    review_parser.add_argument("--fact-id", action="append", default=[])
    review_parser.set_defaults(handler=_review_status)

    return parser.parse_args(argv)


def _error_code(error: BaseException) -> str:
    if isinstance(error, AgentProcessingBlockedError):
        return "LICENSE_BLOCKED"
    if isinstance(error, RecordConflictError):
        return "CONFLICT"
    if isinstance(error, RecordNotFoundError):
        return "UNKNOWN"
    if isinstance(error, RecordTransitionError):
        return "INVALID_STATE"
    if isinstance(error, EvidenceError):
        return "INVALID_EVIDENCE"
    if isinstance(error, RecordValidationError):
        return "INVALID_RECORD"
    return "ERROR"


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        repository = _repository(arguments.repo)
        return int(arguments.handler(repository, arguments))
    except (OSError, ValueError, RepositoryError) as error:
        payload = {
            "status": "ERROR",
            "error_code": _error_code(error),
            "message": str(error),
        }
        print(
            "pcbknowledge: "
            + json.dumps(payload, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
