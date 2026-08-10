"""Safe Agent-facing CLI for Git-native draft preparation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pcbknowledge.git_native.model import (
    KnowledgeRecord,
    LicenseClass,
    PreparedBy,
    RecordStatus,
    deterministic_record_id,
)
from pcbknowledge.git_native.store import (
    ChangeScope,
    KnowledgeRepository,
    RecordConflictError,
    RecordNotFoundError,
    RepositoryError,
)


EDITABLE_FIELDS = (
    "title",
    "document_number",
    "revision",
    "source_locator",
    "source_publisher",
    "license_note",
    "preparation_note",
    "supersedes",
)


def _projection(record: KnowledgeRecord) -> dict[str, Any]:
    return {
        **record.to_dict(),
        "revision_token": record.revision_token,
        "missing_fields": list(record.missing_fields),
        "next_actions": list(record.next_actions),
        "agent_processing_allowed": record.agent_processing_allowed,
    }


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _repository(root: str) -> KnowledgeRepository:
    repository = KnowledgeRepository(Path(root))
    repository.ensure_layout()
    return repository


def _create(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    record_id = deterministic_record_id(arguments.idempotency_key)
    blank = KnowledgeRecord.new(record_id, prepared_by=PreparedBy.AGENT)
    supplied = any(
        getattr(arguments, name) is not None
        for name in (
            "title",
            "document_number",
            "revision",
            "source_locator",
            "source_publisher",
            "license_note",
            "preparation_note",
            "supersedes",
            "pdf",
        )
    ) or arguments.license_class is not LicenseClass.UNKNOWN

    try:
        existing = repository.load(record_id)
    except RecordNotFoundError:
        existing = None
    if existing is not None:
        if existing.prepared_by is not PreparedBy.AGENT:
            raise RecordConflictError("idempotency key belongs to a different origin")
        if supplied:
            desired_evidence = (
                repository.inspect_pdf_path(Path(arguments.pdf))
                if arguments.pdf is not None
                else existing.evidence
            )
            desired = blank.edit(
                title=arguments.title,
                document_number=arguments.document_number,
                revision=arguments.revision,
                source_locator=arguments.source_locator,
                source_publisher=arguments.source_publisher,
                license_class=arguments.license_class,
                license_note=arguments.license_note,
                evidence=desired_evidence,
                preparation_note=arguments.preparation_note,
                supersedes=arguments.supersedes,
            )
            if desired != existing:
                raise RepositoryError(
                    "idempotency key already exists with different content; use draft update"
                )
        _print({**_projection(existing), "replayed": True})
        return 0

    validated = blank.edit(
        title=arguments.title,
        document_number=arguments.document_number,
        revision=arguments.revision,
        source_locator=arguments.source_locator,
        source_publisher=arguments.source_publisher,
        license_class=arguments.license_class,
        license_note=arguments.license_note,
        evidence=blank.evidence,
        preparation_note=arguments.preparation_note,
        supersedes=arguments.supersedes,
    )
    evidence = (
        repository.import_pdf_path(Path(arguments.pdf))
        if arguments.pdf is not None
        else validated.evidence
    )
    updated = blank.edit(
        title=arguments.title,
        document_number=arguments.document_number,
        revision=arguments.revision,
        source_locator=arguments.source_locator,
        source_publisher=arguments.source_publisher,
        license_class=arguments.license_class,
        license_note=arguments.license_note,
        evidence=evidence,
        preparation_note=arguments.preparation_note,
        supersedes=arguments.supersedes,
    )
    repository.insert(updated)
    _print({**_projection(updated), "replayed": False})
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


def _update(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    record = repository.load(arguments.record_id)
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
        "supersedes": _updated_value(arguments, clear, "supersedes", record.supersedes),
    }
    updated = record.edit(evidence=evidence, **values)
    if arguments.pdf is not None:
        evidence = repository.import_pdf_path(Path(arguments.pdf))
        updated = record.edit(evidence=evidence, **values)
    repository.save(record, updated, arguments.expected_revision)
    _print(_projection(updated))
    return 0


def _submit(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    record = repository.load(arguments.record_id)
    updated = record.submit()
    repository.save(record, updated, arguments.expected_revision)
    _print(_projection(updated))
    return 0


def _list(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    records = (
        repository.list_published()
        if arguments.published
        else repository.list(status=arguments.status)
    )
    _print([_projection(record) for record in records])
    return 0


def _show(repository: KnowledgeRepository, arguments: argparse.Namespace) -> int:
    _print(_projection(repository.load(arguments.record_id)))
    return 0


def _validate(repository: KnowledgeRepository, _arguments: argparse.Namespace) -> int:
    records = repository.validate_all(require_canonical=True)
    _print(
        {
            "status": "valid",
            "records": len(records),
            "published_records": len(repository.list_published()),
        }
    )
    return 0


def _diff(repository: KnowledgeRepository, _arguments: argparse.Namespace) -> int:
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


def _add_edit_arguments(parser: argparse.ArgumentParser) -> None:
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Git-native PcbKnowledge drafts")
    parser.add_argument("--repo", default=".", help="repository root (default: current directory)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_mode = list_parser.add_mutually_exclusive_group()
    list_mode.add_argument("--status", type=RecordStatus, choices=tuple(RecordStatus))
    list_mode.add_argument(
        "--published",
        action="store_true",
        help="read committed APPROVED records from HEAD instead of the working tree",
    )
    list_parser.set_defaults(handler=_list, published=False)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("record_id")
    show_parser.set_defaults(handler=_show)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--idempotency-key", required=True)
    _add_edit_arguments(create_parser)
    create_parser.set_defaults(handler=_create, license_class=LicenseClass.UNKNOWN)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("record_id")
    update_parser.add_argument("--expected-revision", required=True)
    _add_edit_arguments(update_parser)
    update_parser.add_argument("--clear", action="append", choices=EDITABLE_FIELDS, default=[])
    update_parser.add_argument("--clear-evidence", action="store_true")
    update_parser.set_defaults(handler=_update)

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("record_id")
    submit_parser.add_argument("--expected-revision", required=True)
    submit_parser.set_defaults(handler=_submit)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.set_defaults(handler=_validate)

    diff_parser = subparsers.add_parser("diff")
    diff_parser.set_defaults(handler=_diff)

    scope_parser = subparsers.add_parser("change-scope")
    scope_parser.set_defaults(handler=_change_scope)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        repository = _repository(arguments.repo)
        return int(arguments.handler(repository, arguments))
    except (OSError, ValueError, RepositoryError) as error:
        print(f"pcbknowledge: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
