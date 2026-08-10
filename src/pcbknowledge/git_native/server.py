"""Loopback-only, server-rendered GUI for the Git-native repository."""

from __future__ import annotations

import argparse
import html
import secrets
import sys
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, cast
from urllib.parse import parse_qs, urlsplit

from pcbknowledge.git_native.model import (
    Evidence,
    KnowledgeRecord,
    LicenseClass,
    PreparedBy,
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
    summarize_records,
)


DEFAULT_PORT = 18080
MAX_FORM_BYTES = MAX_PDF_BYTES + 2 * 1024 * 1024
STATUS_LABELS = {
    RecordStatus.DRAFT: "待准备",
    RecordStatus.READY_FOR_REVIEW: "待审阅",
    RecordStatus.APPROVED: "已批准",
    RecordStatus.REJECTED: "已退回",
}
MISSING_LABELS = {
    "title": "标题",
    "revision": "版本",
    "source": "来源",
    "license": "许可",
    "evidence": "PDF 原件",
}


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
        self.csrf_token = secrets.token_urlsafe(32)


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _hidden(name: str, value: str) -> str:
    return f'<input type="hidden" name="{_escape(name)}" value="{_escape(value)}">'


def _text_field(
    label: str,
    name: str,
    value: str | None,
    *,
    placeholder: str = "",
) -> str:
    return (
        '<label class="field">'
        f"<span>{_escape(label)}</span>"
        f'<input name="{_escape(name)}" value="{_escape(value)}" '
        f'placeholder="{_escape(placeholder)}">'
        "</label>"
    )


def _textarea(label: str, name: str, value: str | None, *, placeholder: str = "") -> str:
    return (
        '<label class="field field-wide">'
        f"<span>{_escape(label)}</span>"
        f'<textarea name="{_escape(name)}" placeholder="{_escape(placeholder)}">'
        f"{_escape(value)}</textarea></label>"
    )


def _license_select(selected: LicenseClass) -> str:
    labels = {
        LicenseClass.UNKNOWN: "未知（不能批准）",
        LicenseClass.OPEN: "开放资料",
        LicenseClass.INTERNAL: "内部可用",
        LicenseClass.RESTRICTED: "受限资料",
    }
    options = "".join(
        f'<option value="{item.value}"{" selected" if item is selected else ""}>'
        f"{_escape(labels[item])}</option>"
        for item in LicenseClass
    )
    return (
        '<label class="field"><span>许可类别</span>'
        f'<select name="license_class">{options}</select></label>'
    )


def _record_form(
    *,
    action: str,
    csrf_token: str,
    record: KnowledgeRecord,
    submit_label: str,
    expected_revision: str | None,
) -> str:
    evidence = ""
    if record.evidence.present:
        evidence = (
            '<div class="evidence-current">'
            '<strong>当前原件</strong>'
            f'<a href="/records/{_escape(record.id)}/evidence" target="_blank" rel="noreferrer">'
            f"{_escape(record.evidence.sha256)}</a>"
            f"<span>{record.evidence.byte_size} bytes</span>"
            "</div>"
        )
    return (
        f'<form class="record-form" action="{_escape(action)}" method="post" '
        'enctype="multipart/form-data">'
        f"{_hidden('csrf_token', csrf_token)}"
        f"{_hidden('expected_revision', expected_revision or '')}"
        '<section class="panel"><div class="section-heading"><div>'
        '<p class="eyebrow">资料身份</p><h2>只填写已经确认的内容</h2>'
        "</div><p>未知项可以留空，批准前会再次校验。</p></div>"
        '<div class="form-grid">'
        f'{_text_field("标题", "title", record.title, placeholder="例如：TPS5430 数据手册")}'
        f'{_text_field("资料编号（可选）", "document_number", record.document_number)}'
        f'{_text_field("版本 / 修订", "revision", record.revision, placeholder="例如：Rev. G")}'
        f'{_text_field("来源发布者", "source_publisher", record.source.publisher)}'
        f'{_text_field("来源 URL 或线索", "source_locator", record.source.locator)}'
        f"{_license_select(record.license_class)}"
        f'{_textarea("许可说明", "license_note", record.license_note)}'
        f'{_textarea("准备说明", "preparation_note", record.preparation_note, placeholder="给 Agent 或审阅者的说明")}'
        f'{_text_field("取代的记录 ID（可选）", "supersedes", record.supersedes)}'
        '<label class="field field-wide"><span>PDF 原件（最大 64 MiB）</span>'
        '<input name="pdf" type="file" accept="application/pdf,.pdf">'
        '</label>'
        f"{evidence}"
        "</div></section>"
        f'<div class="form-actions"><button class="button primary" type="submit">'
        f"{_escape(submit_label)}</button></div></form>"
    )


def _status_badge(record: KnowledgeRecord) -> str:
    css = record.status.value.lower()
    return f'<span class="badge status-{css}">{STATUS_LABELS[record.status]}</span>'


def _missing_badges(record: KnowledgeRecord) -> str:
    if not record.missing_fields:
        return '<span class="badge complete">必需信息完整</span>'
    return "".join(
        f'<span class="badge missing">缺少：{_escape(MISSING_LABELS[item])}</span>'
        for item in record.missing_fields
    )


def _page(title: str, body: str, *, changes: int, active: str = "") -> str:
    def nav(path: str, label: str, key: str) -> str:
        current = ' aria-current="page" class="active"' if active == key else ""
        return f'<a href="{path}"{current}>{label}</a>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)} · PcbKnowledge</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/"><span>PK</span><strong>PcbKnowledge</strong></a>
    <nav>
      {nav('/', '资料工作台', 'records')}
      {nav('/diff', f'查看变化 ({changes})', 'diff')}
    </nav>
  </header>
  <main>{body}</main>
  <footer>本机 Git 工作树是唯一权威数据源 · 保存不会自动提交</footer>
</body>
</html>
"""


class EditorRequestHandler(BaseHTTPRequestHandler):
    server_version = "PcbKnowledgeLocal/1"

    @property
    def editor_server(self) -> EditorHTTPServer:
        return cast(EditorHTTPServer, self.server)

    @property
    def repository(self) -> KnowledgeRepository:
        return self.editor_server.repository

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
            self._send_error_page(HTTPStatus.NOT_FOUND, "没有找到这条记录。")
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
            self._send_error_page(HTTPStatus.NOT_FOUND, "没有找到这条记录。")
        except RecordConflictError as error:
            self._send_error_page(HTTPStatus.CONFLICT, str(error))
        except RecordTransitionError as error:
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
        if path == "/":
            selected: RecordStatus | None = None
            query = parse_qs(parsed.query)
            if query.get("status"):
                try:
                    selected = RecordStatus(query["status"][0])
                except ValueError as error:
                    raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "未知的状态筛选。") from error
            self._dashboard(selected)
            return
        if path == "/records/new":
            record = KnowledgeRecord.new(
                f"pk_{secrets.token_hex(12)}", prepared_by=PreparedBy.HUMAN
            )
            changes = self.repository.git_changes().count
            body = (
                '<div class="page-heading"><div><p class="eyebrow">新建资料</p>'
                '<h1>建立一条可审阅的记录</h1>'
                '<p>先保存草稿，再让 Agent 或同事补充。保存不会提交 Git。</p></div>'
                '<a class="button secondary" href="/">返回工作台</a></div>'
                + _record_form(
                    action="/records/new",
                    csrf_token=self.editor_server.csrf_token,
                    record=record,
                    submit_label="保存新草稿",
                    expected_revision=None,
                )
            )
            self._send_html(_page("新建资料", body, changes=changes, active="records"))
            return
        if path == "/diff":
            self._diff_page()
            return
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "records":
            self._record_page(parts[1])
            return
        if len(parts) == 3 and parts[0] == "records" and parts[2] == "evidence":
            self._serve_evidence(parts[1])
            return
        raise HTTPRequestError(HTTPStatus.NOT_FOUND, "页面不存在。")

    def _dispatch_post(self, form: FormData) -> None:
        path = urlsplit(self.path).path
        if path == "/records/new":
            base = KnowledgeRecord.new(
                f"pk_{secrets.token_hex(12)}", prepared_by=PreparedBy.HUMAN
            )
            record = self._apply_form(base, form)
            self.repository.insert(record)
            self._redirect(f"/records/{record.id}")
            return
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "records":
            raise HTTPRequestError(HTTPStatus.NOT_FOUND, "操作不存在。")
        record_id, action = parts[1], parts[2]
        current = self.repository.load(record_id)
        expected = form.fields.get("expected_revision", "")
        if current.revision_token != expected:
            raise RecordConflictError("记录已经被其他操作修改，请刷新后重试。")
        if action == "save":
            updated = self._apply_form(current, form)
        elif action == "submit":
            updated = current.submit()
        elif action == "approve":
            updated = current.approve(form.fields.get("review_comment"))
        elif action == "reject":
            updated = current.reject(form.fields.get("review_comment"))
        else:
            raise HTTPRequestError(HTTPStatus.NOT_FOUND, "操作不存在。")
        self.repository.save(current, updated, expected)
        self._redirect(f"/records/{record_id}")

    def _apply_form(self, record: KnowledgeRecord, form: FormData) -> KnowledgeRecord:
        raw_license = form.fields.get("license_class", LicenseClass.UNKNOWN.value)
        try:
            license_class = LicenseClass(raw_license)
        except ValueError as error:
            raise RecordValidationError("未知的许可类别") from error
        values = {
            "title": form.fields.get("title"),
            "document_number": form.fields.get("document_number"),
            "revision": form.fields.get("revision"),
            "source_locator": form.fields.get("source_locator"),
            "source_publisher": form.fields.get("source_publisher"),
            "license_class": license_class,
            "license_note": form.fields.get("license_note"),
            "preparation_note": form.fields.get("preparation_note"),
            "supersedes": form.fields.get("supersedes"),
        }
        candidate = record.edit(evidence=record.evidence, **values)
        uploaded = form.files.get("pdf")
        if uploaded is None or not uploaded.payload:
            return candidate
        evidence = self.repository.import_pdf_bytes(uploaded.payload)
        return record.edit(
            evidence=evidence,
            **values,
        )

    def _dashboard(self, selected: RecordStatus | None) -> None:
        all_records = self.repository.list()
        records = all_records if selected is None else [r for r in all_records if r.status is selected]
        summary = summarize_records(all_records)
        changes = self.repository.git_changes()
        filters = [('<a href="/" class="filter">全部</a>' if selected is not None else '<a href="/" class="filter selected">全部</a>')]
        for status in RecordStatus:
            css = "filter selected" if selected is status else "filter"
            filters.append(
                f'<a href="/?status={status.value}" class="{css}">'
                f"{STATUS_LABELS[status]} {summary[status.value]}</a>"
            )
        cards = "".join(
            f'<a class="record-card" href="/records/{_escape(record.id)}">'
            '<div class="record-card-top">'
            f'<div><p class="record-origin">{"AI 准备" if record.prepared_by is PreparedBy.AGENT else "人工录入"}</p>'
            f'<h3>{_escape(record.title or "未命名草稿")}</h3></div>{_status_badge(record)}</div>'
            f'<p class="record-meta">{_escape(record.document_number or "未填资料编号")} · '
            f'{_escape(record.revision or "版本未知")}</p>'
            f'<div class="badges">{_missing_badges(record)}</div></a>'
            for record in records
        )
        if not cards:
            cards = (
                '<section class="empty"><h2>这里还没有记录</h2>'
                '<p>可以由你新建，也可以让 Agent CLI 先准备草稿。</p>'
                '<a class="button primary" href="/records/new">建立第一条资料</a></section>'
            )
        body = (
            '<section class="hero"><div><p class="eyebrow">Git-native · 本机工作树</p>'
            '<h1>Agent 准备，人来确认，Git 负责追踪</h1>'
            '<p>没有账号和数据库。每次保存都是清楚可读的仓库变化，确认后再由你提交。</p>'
            '</div><div class="hero-actions"><a class="button primary" href="/records/new">新建资料</a>'
            f'<a class="button secondary" href="/diff">查看 {changes.count} 项变化</a></div></section>'
            '<section class="stats">'
            f'<div><strong>{summary[RecordStatus.DRAFT.value]}</strong><span>待准备</span></div>'
            f'<div><strong>{summary[RecordStatus.READY_FOR_REVIEW.value]}</strong><span>待审阅</span></div>'
            f'<div><strong>{summary[RecordStatus.APPROVED.value]}</strong><span>已批准</span></div>'
            f'<div><strong>{changes.count}</strong><span>Git 变化</span></div></section>'
            f'<div class="filters">{"".join(filters)}</div><section class="record-grid">{cards}</section>'
        )
        self._send_html(_page("资料工作台", body, changes=changes.count, active="records"))

    def _record_page(self, record_id: str) -> None:
        record = self.repository.load(record_id)
        changes = self.repository.git_changes().count
        heading = (
            '<div class="page-heading"><div>'
            f'<p class="eyebrow">{"AI 准备" if record.prepared_by is PreparedBy.AGENT else "人工录入"}</p>'
            f'<h1>{_escape(record.title or "未命名草稿")}</h1>'
            '<p>记录文件可直接通过 Git diff 审阅；批准后不能原地改写。</p></div>'
            f'<div class="heading-actions">{_status_badge(record)}'
            '<a class="button secondary" href="/">返回工作台</a></div></div>'
            f'<div class="badges record-missing">{_missing_badges(record)}</div>'
        )
        if record.status in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
            if record.status is RecordStatus.REJECTED:
                heading += (
                    '<div class="notice warning"><strong>上次审阅已退回</strong>'
                    f'<p>{_escape(record.review.comment)}</p></div>'
                )
            content = _record_form(
                action=f"/records/{record.id}/save",
                csrf_token=self.editor_server.csrf_token,
                record=record,
                submit_label="保存草稿",
                expected_revision=record.revision_token,
            )
            content += (
                f'<form class="inline-action" action="/records/{record.id}/submit" method="post">'
                f"{_hidden('csrf_token', self.editor_server.csrf_token)}"
                f"{_hidden('expected_revision', record.revision_token)}"
                '<div><strong>准备完成了吗？</strong><p>送审后内容冻结，审阅者可批准或退回。</p></div>'
                '<button class="button primary" type="submit">提交人工审阅</button></form>'
            )
        elif record.status is RecordStatus.READY_FOR_REVIEW:
            content = self._readonly_record(record)
            content += (
                '<section class="panel review-panel"><p class="eyebrow">人工决定</p>'
                '<h2>核对来源、许可、版本和 PDF 原件</h2>'
                '<p>批准会使该记录不可原地修改。退回必须说明下一步。</p>'
                f'<form action="/records/{record.id}/approve" method="post">'
                f"{_hidden('csrf_token', self.editor_server.csrf_token)}"
                f"{_hidden('expected_revision', record.revision_token)}"
                '<label class="field field-wide"><span>批准说明（可选）</span>'
                '<textarea name="review_comment"></textarea></label>'
                '<button class="button primary" type="submit">批准这条资料</button></form>'
                f'<form action="/records/{record.id}/reject" method="post">'
                f"{_hidden('csrf_token', self.editor_server.csrf_token)}"
                f"{_hidden('expected_revision', record.revision_token)}"
                '<label class="field field-wide"><span>退回原因（必填）</span>'
                '<textarea name="review_comment" required></textarea></label>'
                '<button class="button danger" type="submit">退回补充</button></form></section>'
            )
        else:
            content = (
                '<div class="notice success"><strong>这条资料已经批准并锁定</strong>'
                '<p>如需修正，请新建记录并填写“取代的记录 ID”。</p></div>'
                + self._readonly_record(record)
            )
        self._send_html(
            _page(
                record.title or "未命名草稿",
                heading + content,
                changes=changes,
                active="records",
            )
        )

    def _readonly_record(self, record: KnowledgeRecord) -> str:
        evidence = "未提供"
        if record.evidence.present:
            evidence = (
                f'<a href="/records/{record.id}/evidence" target="_blank" rel="noreferrer">'
                f"打开 PDF · {_escape(record.evidence.sha256)}</a>"
            )
        rows = (
            ("资料编号", record.document_number or "未知"),
            ("版本", record.revision or "未知"),
            ("发布者", record.source.publisher or "未知"),
            ("来源", record.source.locator or "未知"),
            ("许可", record.license_class.value),
            ("原件", evidence),
        )
        items = "".join(
            f'<div><dt>{_escape(label)}</dt><dd>{value if label == "原件" else _escape(value)}</dd></div>'
            for label, value in rows
        )
        note = _escape(record.preparation_note or "无")
        return (
            f'<section class="panel"><dl class="record-details">{items}</dl>'
            f'<div class="note"><strong>准备说明</strong><p>{note}</p></div></section>'
        )

    def _diff_page(self) -> None:
        changes = self.repository.git_changes()
        status = "\n".join(changes.status_lines) or "工作树中没有 knowledge/evidence 变化。"
        diff = changes.tracked_diff + changes.untracked_preview
        if not diff:
            diff = "暂无可显示的内容差异。"
        body = (
            '<div class="page-heading"><div><p class="eyebrow">提交前检查</p>'
            '<h1>仓库变化</h1><p>这里只预览，不会执行 add、commit 或 push。</p></div>'
            '<a class="button secondary" href="/">返回工作台</a></div>'
            '<section class="panel diff-panel"><h2>Git 状态</h2>'
            f'<pre>{_escape(status)}</pre><h2>内容差异与新文件预览</h2>'
            f'<pre>{_escape(diff)}</pre></section>'
        )
        self._send_html(_page("仓库变化", body, changes=changes.count, active="diff"))

    def _serve_evidence(self, record_id: str) -> None:
        record = self.repository.load(record_id)
        self.repository.verify_evidence(record.evidence)
        if not record.evidence.present or record.evidence.path is None:
            raise HTTPRequestError(HTTPStatus.NOT_FOUND, "这条记录没有 PDF 原件。")
        payload = (self.repository.root / record.evidence.path).read_bytes()
        self.send_response(HTTPStatus.OK)
        self._security_headers(cache="no-store")
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{record.id}.pdf"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_form(self) -> FormData:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise HTTPRequestError(HTTPStatus.LENGTH_REQUIRED, "请求缺少 Content-Length。")
        try:
            length = int(content_length)
        except ValueError as error:
            raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "Content-Length 无效。") from error
        if length < 0 or length > MAX_FORM_BYTES:
            raise HTTPRequestError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "上传内容超过 64 MiB。")
        body = self.rfile.read(length)
        if len(body) != length:
            raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "请求内容不完整。")
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("application/x-www-form-urlencoded"):
            decoded = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
            if any(len(values) != 1 for values in decoded.values()):
                raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "表单字段重复。")
            return FormData(fields={key: values[0] for key, values in decoded.items()}, files={})
        if content_type.startswith("multipart/form-data"):
            envelope = (
                f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
                + body
            )
            message = BytesParser(policy=policy.default).parsebytes(envelope)
            if not message.is_multipart():
                raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "multipart 表单无效。")
            fields: dict[str, str] = {}
            files: dict[str, UploadedFile] = {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not isinstance(name, str) or not name:
                    raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "multipart 字段缺少名称。")
                filename = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if filename is not None:
                    if name in files:
                        raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "上传字段重复。")
                    if payload:
                        files[name] = UploadedFile(filename=filename, payload=payload)
                    continue
                if name in fields:
                    raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "表单字段重复。")
                try:
                    fields[name] = payload.decode(part.get_content_charset() or "utf-8")
                except UnicodeDecodeError as error:
                    raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "表单字段不是 UTF-8。") from error
            return FormData(fields=fields, files=files)
        raise HTTPRequestError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "不支持的表单格式。")

    def _require_csrf(self, form: FormData) -> None:
        supplied = form.fields.get("csrf_token", "")
        if not secrets.compare_digest(supplied, self.editor_server.csrf_token):
            raise HTTPRequestError(HTTPStatus.FORBIDDEN, "页面令牌已过期，请刷新后重试。")
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
            raise HTTPRequestError(HTTPStatus.FORBIDDEN, "拒绝非本机来源的修改请求。")

    def _require_loopback_host(self) -> None:
        host = self.headers.get("Host", "")
        try:
            parsed = urlsplit(f"//{host}")
            port = parsed.port
        except ValueError as error:
            raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "Host 无效。") from error
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "只接受本机访问。")
        if port is not None and port != self.editor_server.server_port:
            raise HTTPRequestError(HTTPStatus.BAD_REQUEST, "Host 端口不匹配。")

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self._security_headers(cache="no-store")
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_html(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(status, payload.encode("utf-8"), "text/html; charset=utf-8")

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

    def _send_error_page(self, status: HTTPStatus, message: str) -> None:
        try:
            changes = self.repository.git_changes().count
        except RepositoryError:
            changes = 0
        body = (
            '<section class="error-page"><p class="eyebrow">操作未完成</p>'
            f'<h1>{status.value} · {_escape(status.phrase)}</h1>'
            f'<p>{_escape(message)}</p><a class="button primary" href="/">返回工作台</a></section>'
        )
        self._send_html(_page("操作未完成", body, changes=changes), status)


def create_server(repository_root: Path, port: int = DEFAULT_PORT) -> EditorHTTPServer:
    repository = KnowledgeRepository(repository_root)
    repository.ensure_layout()
    repository.validate_all(require_canonical=True)
    return EditorHTTPServer(("127.0.0.1", port), repository)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Git-native PcbKnowledge editor")
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
