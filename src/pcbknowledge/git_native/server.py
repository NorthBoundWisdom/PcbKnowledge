"""Loopback-only HTTP transport for the typed PcbKnowledge workbench."""

from __future__ import annotations

import argparse
import secrets
import sys
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Mapping, cast
from urllib.parse import parse_qs, urlsplit

from pcbknowledge.git_native.model import (
    EntityKind,
    LicenseClass,
    RecordStatus,
    RecordTransitionError,
    RecordValidationError,
)
from pcbknowledge.git_native.store import (
    EvidenceError,
    KnowledgeRepository,
    MAX_PDF_BYTES,
    RecordConflictError,
    RecordNotFoundError,
    RepositoryError,
)
from pcbknowledge.git_native.workbench import (
    SourceDraftInput,
    WorkbenchApplication,
)
from pcbknowledge.git_native.workbench_views import (
    render_diff,
    render_entity_detail,
    render_entity_list,
    render_error,
    render_fact_detail,
    render_fact_list,
    render_new_source,
    render_review,
    render_source_detail,
    render_source_list,
)


DEFAULT_PORT = 18080
MAX_FORM_BYTES = MAX_PDF_BYTES + 2 * 1024 * 1024


class HTTPRequestError(RuntimeError):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class UploadedFile:
    filename: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class FormData:
    fields: Mapping[str, str]
    files: Mapping[str, UploadedFile]


class EditorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], repository: KnowledgeRepository) -> None:
        super().__init__(address, EditorRequestHandler)
        self.repository = repository
        self.application = WorkbenchApplication(repository)
        self.csrf_token = secrets.token_urlsafe(32)


class EditorRequestHandler(BaseHTTPRequestHandler):
    server_version = "PcbKnowledgeLocal/3"

    @property
    def editor_server(self) -> EditorHTTPServer:
        return cast(EditorHTTPServer, self.server)

    @property
    def repository(self) -> KnowledgeRepository:
        return self.editor_server.repository

    @property
    def application(self) -> WorkbenchApplication:
        return self.editor_server.application

    def log_message(self, format_: str, *arguments: object) -> None:
        try:
            status = int(arguments[1])
        except (IndexError, TypeError, ValueError):
            return
        if status >= HTTPStatus.BAD_REQUEST:
            sys.stderr.write(f"[pcbknowledge] {format_ % arguments}\n")

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._require_loopback_host()
            self._dispatch_get()
        except HTTPRequestError as error:
            self._send_error_page(error.status, str(error))
        except RecordNotFoundError:
            self._send_error_page(HTTPStatus.NOT_FOUND, "Record not found.")
        except (RecordValidationError, EvidenceError, RepositoryError) as error:
            self._send_error_page(HTTPStatus.BAD_REQUEST, str(error))

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._require_loopback_host()
            form = self._read_form()
            self._require_csrf(form)
            self._dispatch_post(form)
        except HTTPRequestError as error:
            self._send_error_page(error.status, str(error))
        except RecordNotFoundError:
            self._send_error_page(HTTPStatus.NOT_FOUND, "Record not found.")
        except (RecordConflictError, RecordTransitionError) as error:
            self._send_error_page(HTTPStatus.CONFLICT, str(error))
        except (RecordValidationError, EvidenceError, RepositoryError, ValueError) as error:
            self._send_error_page(HTTPStatus.BAD_REQUEST, str(error))

    def _dispatch_get(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/healthz":
            self._send_bytes(HTTPStatus.OK, b"ok\n", "text/plain; charset=utf-8")
            return
        if path == "/static/app.css":
            stylesheet = Path(__file__).with_name("static") / "app.css"
            self._send_bytes(
                HTTPStatus.OK,
                stylesheet.read_bytes(),
                "text/css; charset=utf-8",
                cache="public, max-age=3600",
            )
            return
        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self._security_headers(cache="public, max-age=86400")
            self.end_headers()
            return
        if path in {"/", "/review"}:
            overview = self.application.overview()
            self._send_html(render_review(overview, workspace=self.repository.root))
            return
        if path == "/sources":
            selected = self._status_filter(parsed.query)
            sources = self.application.list_sources(status=selected)
            self._send_html(
                render_source_list(
                    sources,
                    workspace=self.repository.root,
                    change_count=self.repository.git_changes().count,
                    selected_status=None if selected is None else selected.value,
                )
            )
            return
        if path == "/sources/new":
            self._send_html(
                render_new_source(
                    workspace=self.repository.root,
                    change_count=self.repository.git_changes().count,
                    csrf_token=self.editor_server.csrf_token,
                )
            )
            return
        if path == "/entities":
            selected = self._entity_kind_filter(parsed.query)
            entities = self.application.list_entities(kind=selected)
            self._send_html(
                render_entity_list(
                    entities,
                    workspace=self.repository.root,
                    change_count=self.repository.git_changes().count,
                    selected_kind=None if selected is None else selected.value,
                )
            )
            return
        if path == "/facts":
            selected = self._status_filter(parsed.query)
            facts = self.application.list_facts(status=selected)
            self._send_html(
                render_fact_list(
                    facts,
                    workspace=self.repository.root,
                    change_count=self.repository.git_changes().count,
                    selected_status=None if selected is None else selected.value,
                )
            )
            return
        if path == "/diff":
            self._diff_page()
            return

        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "sources":
            source = self.application.source_detail(parts[1])
            decision = (
                self.application.source_review_decision(parts[1])
                if source.status == RecordStatus.READY_FOR_REVIEW.value
                else None
            )
            self._send_html(
                render_source_detail(
                    source,
                    workspace=self.repository.root,
                    change_count=self.repository.git_changes().count,
                    csrf_token=self.editor_server.csrf_token,
                    decision=decision,
                )
            )
            return
        if len(parts) == 3 and parts[0] == "sources" and parts[2] == "evidence":
            self._serve_evidence(parts[1])
            return
        if len(parts) == 2 and parts[0] == "entities":
            entity = self.application.entity_detail(parts[1])
            self._send_html(
                render_entity_detail(
                    entity,
                    workspace=self.repository.root,
                    change_count=self.repository.git_changes().count,
                )
            )
            return
        if len(parts) == 2 and parts[0] == "facts":
            fact = self.application.fact_detail(parts[1])
            decision = (
                self.application.fact_review_decision(parts[1])
                if fact.status == RecordStatus.READY_FOR_REVIEW.value
                else None
            )
            self._send_html(
                render_fact_detail(
                    fact,
                    workspace=self.repository.root,
                    change_count=self.repository.git_changes().count,
                    csrf_token=self.editor_server.csrf_token,
                    decision=decision,
                )
            )
            return
        raise HTTPRequestError(HTTPStatus.NOT_FOUND, "Page not found.")

    def _dispatch_post(self, form: FormData) -> None:
        path = urlsplit(self.path).path
        if path == "/sources/new":
            draft = self._source_draft(form)
            uploaded = form.files.get("pdf")
            source = self.application.create_source(
                draft,
                pdf_payload=None if uploaded is None else uploaded.payload,
            )
            self._redirect(f"/sources/{source.id}")
            return

        parts = path.strip("/").split("/")
        if len(parts) != 3:
            raise HTTPRequestError(HTTPStatus.NOT_FOUND, "Operation not found.")
        record_id, action = parts[1], parts[2]
        expected = form.fields.get("expected_revision", "")

        if parts[0] == "sources":
            if action == "save":
                draft = self._source_draft(form)
                uploaded = form.files.get("pdf")
                self.application.update_source(
                    record_id,
                    expected_revision=expected,
                    draft=draft,
                    pdf_payload=None if uploaded is None else uploaded.payload,
                )
            elif action == "submit":
                self.application.submit_source(
                    record_id, expected_revision=expected
                )
            elif action == "approve":
                self.application.approve_source(
                    record_id,
                    expected_revision=expected,
                    comment=form.fields.get("review_comment"),
                )
            elif action == "reject":
                self.application.reject_source(
                    record_id,
                    expected_revision=expected,
                    comment=form.fields.get("review_comment", ""),
                )
            else:
                raise HTTPRequestError(HTTPStatus.NOT_FOUND, "Operation not found.")
            self._redirect(f"/sources/{record_id}")
            return

        if parts[0] == "facts":
            if action == "approve":
                self.application.approve_fact(
                    record_id,
                    expected_revision=expected,
                    comment=form.fields.get("review_comment"),
                )
            elif action == "reject":
                self.application.reject_fact(
                    record_id,
                    expected_revision=expected,
                    comment=form.fields.get("review_comment", ""),
                )
            else:
                raise HTTPRequestError(HTTPStatus.NOT_FOUND, "Operation not found.")
            self._redirect(f"/facts/{record_id}")
            return

        raise HTTPRequestError(HTTPStatus.NOT_FOUND, "Operation not found.")

    @staticmethod
    def _status_filter(query_string: str) -> RecordStatus | None:
        query = parse_qs(query_string)
        if not query.get("status"):
            return None
        try:
            return RecordStatus(query["status"][0])
        except ValueError as error:
            raise HTTPRequestError(
                HTTPStatus.BAD_REQUEST, "Unknown status filter."
            ) from error

    @staticmethod
    def _entity_kind_filter(query_string: str) -> EntityKind | None:
        query = parse_qs(query_string)
        if not query.get("kind"):
            return None
        try:
            return EntityKind(query["kind"][0])
        except ValueError as error:
            raise HTTPRequestError(
                HTTPStatus.BAD_REQUEST, "Unknown entity-kind filter."
            ) from error

    @staticmethod
    def _source_draft(form: FormData) -> SourceDraftInput:
        raw_license = form.fields.get("license_class", LicenseClass.UNKNOWN.value)
        try:
            license_class = LicenseClass(raw_license)
        except ValueError as error:
            raise RecordValidationError("Unknown license class") from error
        return SourceDraftInput(
            title=form.fields.get("title"),
            document_number=form.fields.get("document_number"),
            revision=form.fields.get("revision"),
            source_publisher=form.fields.get("source_publisher"),
            source_locator=form.fields.get("source_locator"),
            license_class=license_class,
            license_note=form.fields.get("license_note"),
            preparation_note=form.fields.get("preparation_note"),
            supersedes=form.fields.get("supersedes"),
        )

    def _diff_page(self) -> None:
        changes = self.repository.git_changes()
        status_text = (
            "\n".join(changes.status_lines)
            or "No knowledge/evidence changes in the working tree."
        )
        diff_text = changes.tracked_diff + changes.untracked_preview
        if not diff_text:
            diff_text = "No content diff to display."
        self._send_html(
            render_diff(
                status_text=status_text,
                diff_text=diff_text,
                workspace=self.repository.root,
                change_count=changes.count,
            )
        )

    def _serve_evidence(self, source_id: str) -> None:
        source = self.repository.load_source(source_id)
        self.repository.verify_evidence(source.evidence)
        if not source.evidence.present or source.evidence.path is None:
            raise HTTPRequestError(
                HTTPStatus.NOT_FOUND, "This Source has no PDF original."
            )
        payload = (self.repository.root / source.evidence.path).read_bytes()
        self.send_response(HTTPStatus.OK)
        self._security_headers(cache="no-store")
        self.send_header("Content-Type", "application/pdf")
        self.send_header(
            "Content-Disposition", f'inline; filename="{source.id}.pdf"'
        )
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_form(self) -> FormData:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise HTTPRequestError(
                HTTPStatus.LENGTH_REQUIRED, "Request is missing Content-Length."
            )
        try:
            length = int(content_length)
        except ValueError as error:
            raise HTTPRequestError(
                HTTPStatus.BAD_REQUEST, "Invalid Content-Length."
            ) from error
        if length < 0 or length > MAX_FORM_BYTES:
            raise HTTPRequestError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "Upload exceeds 64 MiB.",
            )
        body = self.rfile.read(length)
        if len(body) != length:
            raise HTTPRequestError(
                HTTPStatus.BAD_REQUEST, "Request body is incomplete."
            )
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("application/x-www-form-urlencoded"):
            decoded = parse_qs(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
            if any(len(values) != 1 for values in decoded.values()):
                raise HTTPRequestError(
                    HTTPStatus.BAD_REQUEST, "Duplicate form field."
                )
            return FormData(
                fields={key: values[0] for key, values in decoded.items()},
                files={},
            )
        if content_type.startswith("multipart/form-data"):
            envelope = (
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode(
                    "ascii"
                )
                + body
            )
            message = BytesParser(policy=policy.default).parsebytes(envelope)
            if not message.is_multipart():
                raise HTTPRequestError(
                    HTTPStatus.BAD_REQUEST, "Invalid multipart form."
                )
            fields: dict[str, str] = {}
            files: dict[str, UploadedFile] = {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not isinstance(name, str) or not name:
                    raise HTTPRequestError(
                        HTTPStatus.BAD_REQUEST,
                        "Multipart field is missing a name.",
                    )
                filename = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if filename is not None:
                    if name in files:
                        raise HTTPRequestError(
                            HTTPStatus.BAD_REQUEST,
                            "Duplicate upload field.",
                        )
                    if payload:
                        files[name] = UploadedFile(
                            filename=filename, payload=payload
                        )
                    continue
                if name in fields:
                    raise HTTPRequestError(
                        HTTPStatus.BAD_REQUEST, "Duplicate form field."
                    )
                try:
                    fields[name] = payload.decode(
                        part.get_content_charset() or "utf-8"
                    )
                except UnicodeDecodeError as error:
                    raise HTTPRequestError(
                        HTTPStatus.BAD_REQUEST,
                        "Form field is not UTF-8.",
                    ) from error
            return FormData(fields=fields, files=files)
        raise HTTPRequestError(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Unsupported form format."
        )

    def _require_csrf(self, form: FormData) -> None:
        supplied = form.fields.get("csrf_token", "")
        if not secrets.compare_digest(
            supplied, self.editor_server.csrf_token
        ):
            raise HTTPRequestError(
                HTTPStatus.FORBIDDEN,
                "Page token expired. Refresh and retry.",
            )
        origin = self.headers.get("Origin")
        if origin is None:
            return
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.port != self.editor_server.server_port
            or parsed.path not in {"", "/"}
        ):
            raise HTTPRequestError(
                HTTPStatus.FORBIDDEN,
                "Mutation request rejected from non-loopback origin.",
            )

    def _require_loopback_host(self) -> None:
        host = self.headers.get("Host", "")
        try:
            parsed = urlsplit(f"//{host}")
            port = parsed.port
        except ValueError as error:
            raise HTTPRequestError(
                HTTPStatus.BAD_REQUEST, "Invalid Host header."
            ) from error
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise HTTPRequestError(
                HTTPStatus.BAD_REQUEST,
                "Only loopback access is accepted.",
            )
        if port is not None and port != self.editor_server.server_port:
            raise HTTPRequestError(
                HTTPStatus.BAD_REQUEST,
                "Host port does not match the editor port.",
            )

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self._security_headers(cache="no-store")
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_html(
        self, payload: str, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        self._send_bytes(
            status, payload.encode("utf-8"), "text/html; charset=utf-8"
        )

    def _send_bytes(
        self,
        status: HTTPStatus,
        payload: bytes,
        content_type: str,
        *,
        cache: str = "no-store",
    ) -> None:
        self.send_response(status)
        self._security_headers(cache=cache)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _security_headers(self, *, cache: str) -> None:
        self.send_header("Cache-Control", cache)
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'self'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _send_error_page(
        self, status: HTTPStatus, message: str
    ) -> None:
        try:
            changes = self.repository.git_changes().count
        except RepositoryError:
            changes = 0
        self._send_html(
            render_error(
                status_code=status.value,
                status_phrase=status.phrase,
                message=message,
                workspace=self.repository.root,
                change_count=changes,
            ),
            status,
        )


def create_server(
    repository_root: Path, port: int = DEFAULT_PORT
) -> EditorHTTPServer:
    repository = KnowledgeRepository(repository_root)
    repository.ensure_layout()
    repository.validate_all(require_canonical=True)
    return EditorHTTPServer(("127.0.0.1", port), repository)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the typed Git-native PcbKnowledge workbench"
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        server = create_server(Path(arguments.repo), arguments.port)
    except (OSError, RecordValidationError, RepositoryError) as error:
        print(f"pcbknowledge: {error}", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"[pcbknowledge] GUI ready: {url}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
