"""Read-only review-closure projection and human decision gates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Iterable

from pcbknowledge.git_native.model import (
    EntityKind,
    FactRecord,
    RecordStatus,
    RecordTransitionError,
    SourceRecord,
)
from pcbknowledge.git_native.store import (
    ChangeScope,
    KnowledgeRepository,
    RecordNotFoundError,
    RepositoryError,
)


_ALLOWED_DECISION_SCOPES = {ChangeScope.CLEAN, ChangeScope.DATA_ONLY}


@dataclass(frozen=True, slots=True)
class SelectedChangeView:
    paths: tuple[str, ...]
    status_lines: tuple[str, ...]
    diff_text: str


@dataclass(frozen=True, slots=True)
class ReviewDecisionView:
    kind: str
    record_id: str
    status: str
    change_scope: str
    scope_blocker: str | None
    approval_blockers: tuple[str, ...]
    decision_blockers: tuple[str, ...]
    can_approve: bool
    can_reject: bool
    selected: SelectedChangeView


class ReviewClosureApplication:
    """Project exact review closure and gate human authority transitions."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    def source_decision(self, source_id: str) -> ReviewDecisionView:
        snapshot = self.repository.validate_all(require_canonical=True)
        source = next((item for item in snapshot.sources if item.id == source_id), None)
        if source is None:
            raise RecordNotFoundError("source not found")

        paths = self._source_paths(source, snapshot.sources)
        scope, scope_blocker = self._scope_state()
        decision_blockers = self._decision_blockers(source.status, scope_blocker)
        approval_blockers = tuple(
            f"Missing {field}" for field in source.missing_fields
        )
        return ReviewDecisionView(
            kind="SOURCE",
            record_id=source.id,
            status=source.status.value,
            change_scope=scope.value,
            scope_blocker=scope_blocker,
            approval_blockers=approval_blockers,
            decision_blockers=decision_blockers,
            can_approve=not approval_blockers and not decision_blockers,
            can_reject=not decision_blockers,
            selected=self._selected_changes(paths),
        )

    def fact_decision(self, fact_id: str) -> ReviewDecisionView:
        snapshot = self.repository.validate_all(require_canonical=True)
        fact = next((item for item in snapshot.facts if item.id == fact_id), None)
        if fact is None:
            raise RecordNotFoundError("fact not found")

        source_map = {source.id: source for source in snapshot.sources}
        conflict_map: dict[str, tuple[str, ...]] = {}
        for conflict in snapshot.conflicts:
            for candidate in conflict.fact_ids:
                conflict_map[candidate] = tuple(
                    other for other in conflict.fact_ids if other != candidate
                )

        approval_blockers = self._fact_approval_blockers(
            fact,
            source_map=source_map,
            conflict_ids=conflict_map.get(fact.id, ()),
        )
        scope, scope_blocker = self._scope_state()
        decision_blockers = self._decision_blockers(fact.status, scope_blocker)
        return ReviewDecisionView(
            kind="FACT",
            record_id=fact.id,
            status=fact.status.value,
            change_scope=scope.value,
            scope_blocker=scope_blocker,
            approval_blockers=approval_blockers,
            decision_blockers=decision_blockers,
            can_approve=not approval_blockers and not decision_blockers,
            can_reject=not decision_blockers,
            selected=self._selected_changes(
                self._fact_paths(fact, snapshot.sources, snapshot.entities)
            ),
        )

    @staticmethod
    def require_approval(decision: ReviewDecisionView) -> None:
        blockers = (*decision.decision_blockers, *decision.approval_blockers)
        if blockers:
            raise RecordTransitionError(
                "review approval is blocked: " + "; ".join(blockers)
            )

    @staticmethod
    def require_rejection(decision: ReviewDecisionView) -> None:
        if decision.decision_blockers:
            raise RecordTransitionError(
                "review rejection is blocked: "
                + "; ".join(decision.decision_blockers)
            )

    def _scope_state(self) -> tuple[ChangeScope, str | None]:
        scope = self.repository.git_change_scope()
        if scope in _ALLOWED_DECISION_SCOPES:
            return scope, None
        return (
            scope,
            "Human review decisions require a CLEAN or DATA_ONLY next-commit "
            f"candidate; current scope is {scope.value}.",
        )

    @staticmethod
    def _decision_blockers(
        status: RecordStatus, scope_blocker: str | None
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        if status is not RecordStatus.READY_FOR_REVIEW:
            blockers.append(
                f"Record is {status.value}, not READY_FOR_REVIEW."
            )
        if scope_blocker is not None:
            blockers.append(scope_blocker)
        return tuple(blockers)

    @staticmethod
    def _fact_approval_blockers(
        fact: FactRecord,
        *,
        source_map: dict[str, SourceRecord],
        conflict_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        blockers = [f"Missing {field}" for field in fact.missing_fields]
        if conflict_ids:
            blockers.append(
                "Semantic conflict is unresolved with: "
                + ", ".join(conflict_ids)
            )
        for source_id in fact.source_ids:
            source = source_map[source_id]
            if source.status is not RecordStatus.APPROVED:
                blockers.append(
                    f"Source {source_id} is {source.status.value}, not APPROVED"
                )
            if not source.evidence.present:
                blockers.append(f"Source {source_id} has no PDF evidence")
            if not source.agent_processing_allowed:
                blockers.append(
                    f"Source {source_id} license {source.license_class.value} "
                    "blocks evidence review"
                )
        return tuple(dict.fromkeys(blockers))

    def _source_paths(
        self, source: SourceRecord, sources: Iterable[SourceRecord]
    ) -> tuple[str, ...]:
        paths = [self.repository.source_path(source.id).relative_to(self.repository.root).as_posix()]
        if source.evidence.path is not None:
            paths.append(source.evidence.path)
        if source.supersedes is not None:
            predecessor = next(
                (item for item in sources if item.id == source.supersedes), None
            )
            if predecessor is not None:
                paths.append(
                    self.repository.source_path(predecessor.id)
                    .relative_to(self.repository.root)
                    .as_posix()
                )
        return tuple(dict.fromkeys(paths))

    def _fact_paths(
        self,
        fact: FactRecord,
        sources: Iterable[SourceRecord],
        entities: Iterable[object],
    ) -> tuple[str, ...]:
        source_map = {source.id: source for source in sources}
        entity_map = {getattr(entity, "id"): entity for entity in entities}
        paths = [
            self.repository.fact_path(fact.id)
            .relative_to(self.repository.root)
            .as_posix()
        ]
        if fact.supersedes is not None:
            paths.append(
                self.repository.fact_path(fact.supersedes)
                .relative_to(self.repository.root)
                .as_posix()
            )
        for entity_id in fact.subject_entity_ids:
            paths.append(
                self.repository.entity_path(entity_id)
                .relative_to(self.repository.root)
                .as_posix()
            )
            entity = entity_map.get(entity_id)
            if (
                entity is not None
                and getattr(entity, "kind", None) is EntityKind.COMPONENT
                and getattr(entity, "manufacturer_id", None) is not None
            ):
                manufacturer_id = getattr(entity, "manufacturer_id")
                paths.append(
                    self.repository.entity_path(manufacturer_id)
                    .relative_to(self.repository.root)
                    .as_posix()
                )
        for source_id in fact.source_ids:
            source = source_map[source_id]
            paths.append(
                self.repository.source_path(source_id)
                .relative_to(self.repository.root)
                .as_posix()
            )
            if source.evidence.path is not None:
                paths.append(source.evidence.path)
        return tuple(dict.fromkeys(paths))

    def _selected_changes(self, paths: tuple[str, ...]) -> SelectedChangeView:
        if not paths:
            return SelectedChangeView((), (), "No selected closure paths.\n")
        status = self._git_text(
            "status", "--short", "--untracked-files=all", "--", *paths
        )
        status_lines = tuple(line for line in status.splitlines() if line)
        sections: list[str] = []

        staged = self._git_text(
            "diff", "--cached", "--no-ext-diff", "--", *paths
        )
        if staged:
            sections.extend(("# Staged selected-closure changes\n", staged))

        unstaged = self._git_text(
            "diff", "--no-ext-diff", "--", *paths
        )
        if unstaged:
            sections.extend(("# Unstaged selected-closure changes\n", unstaged))

        untracked = self._git_bytes(
            "ls-files", "--others", "--exclude-standard", "-z", "--", *paths
        )
        for raw_path in untracked.split(b"\0"):
            if not raw_path:
                continue
            try:
                relative = raw_path.decode("utf-8")
            except UnicodeDecodeError as error:
                raise RepositoryError("Git path is not UTF-8") from error
            candidate = (self.repository.root / relative).resolve()
            try:
                candidate.relative_to(self.repository.root)
            except ValueError:
                continue
            if candidate.suffix == ".json" and candidate.is_file():
                sections.append(f"# Untracked selected file: {relative}\n")
                sections.append(f"--- /dev/null\n+++ b/{relative}\n")
                sections.extend(
                    f"+{line}\n"
                    for line in candidate.read_text(encoding="utf-8").splitlines()
                )
            elif candidate.suffix == ".pdf" and candidate.is_file():
                sections.append(
                    f"# Untracked binary evidence: {relative} "
                    f"({candidate.stat().st_size} bytes)\n"
                )

        diff_text = "".join(sections) or "No selected closure changes.\n"
        return SelectedChangeView(
            paths=paths,
            status_lines=status_lines,
            diff_text=diff_text,
        )

    def _git_text(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.repository.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RepositoryError(result.stderr.strip() or "git command failed")
        return result.stdout

    def _git_bytes(self, *arguments: str) -> bytes:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.repository.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise RepositoryError(message or "git command failed")
        return result.stdout
