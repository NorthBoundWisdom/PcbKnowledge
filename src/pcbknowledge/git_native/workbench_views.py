"""Pure HTML rendering for typed PcbKnowledge workbench view models."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable

from pcbknowledge.git_native.workbench import (
    EntityView,
    FactView,
    LinkView,
    ReviewEventView,
    SourceView,
    WorkbenchOverview,
)


LICENSE_LABELS = {
    "UNKNOWN": "Unknown (cannot approve)",
    "PUBLIC_REFERENCE": "Public reference",
    "OPEN_LICENSE": "Open-license material",
    "INTERNAL": "Internal use allowed",
    "RESTRICTED": "Restricted",
    "LICENSED_BLOCKED_FOR_AI": "Licensed material (AI processing blocked)",
}


def escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def hidden(name: str, value: str) -> str:
    return f'<input type="hidden" name="{escape(name)}" value="{escape(value)}">'


def status_label(status: str) -> str:
    return status.replace("_", " ").title()


def status_badge(status: str) -> str:
    return (
        f'<span class="badge status-{escape(status.lower())}">'
        f"{escape(status_label(status))}</span>"
    )


def badge(label: str, tone: str = "") -> str:
    css = f"badge {tone}".strip()
    return f'<span class="{escape(css)}">{escape(label)}</span>'


def link_list(
    links: Iterable[LinkView], *, empty: str = "None"
) -> str:
    values = tuple(links)
    if not values:
        return f'<span class="muted">{escape(empty)}</span>'
    return "".join(
        (
            f'<a class="relation-link" href="{escape(link.href)}">'
            + (
                f'<span>{escape(link.role)}</span>'
                if link.role is not None
                else ""
            )
            + f"<strong>{escape(link.label)}</strong>"
            + f"<code>{escape(link.id)}</code></a>"
        )
        for link in values
    )


def review_history(events: tuple[ReviewEventView, ...]) -> str:
    if not events:
        return '<p class="muted">No review events yet.</p>'
    return (
        '<ol class="timeline">'
        + "".join(
            (
                "<li>"
                f"<strong>{escape(status_label(event.action))}</strong>"
                f"<p>{escape(event.comment or 'No comment')}</p>"
                "</li>"
            )
            for event in events
        )
        + "</ol>"
    )


def page(
    title: str,
    body: str,
    *,
    workspace: Path,
    change_count: int,
    active: str,
) -> str:
    def nav(path: str, label: str, key: str) -> str:
        current = ' aria-current="page" class="active"' if active == key else ""
        return f'<a href="{path}"{current}>{label}</a>'

    workspace_label = escape(str(workspace))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} · PcbKnowledge</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/review"><span>PK</span><strong>PcbKnowledge</strong></a>
    <nav>
      {nav('/review', 'Review', 'review')}
      {nav('/sources', 'Sources', 'sources')}
      {nav('/entities', 'Entities', 'entities')}
      {nav('/facts', 'Facts', 'facts')}
      {nav('/diff', f'Changes ({change_count})', 'diff')}
    </nav>
  </header>
  <main>
    <section class="workspace-strip">
      <div><span>Selected knowledge workspace</span><code>{workspace_label}</code></div>
      <span>Git-native authority · saving never commits</span>
    </section>
    {body}
  </main>
  <footer>Source, Entity, Fact, evidence, and review state come only from the selected workspace.</footer>
</body>
</html>
"""


def render_review(
    overview: WorkbenchOverview, *, workspace: Path
) -> str:
    cards = []
    for item in overview.review_items:
        blockers = (
            "".join(badge(value, "missing") for value in item.blockers)
            if item.blockers
            else badge("Closure ready", "complete")
        )
        cards.append(
            '<a class="review-card" href="{href}">'
            '<div class="record-card-top"><div>'
            '<p class="record-origin">{kind} · {prepared}</p>'
            '<h3>{title}</h3>'
            '<p class="record-meta">{context}</p>'
            '</div>{status}</div>'
            '<div class="badges">{blockers}</div>'
            '</a>'.format(
                href=escape(item.href),
                kind=escape(item.kind),
                prepared=escape(item.prepared_by),
                title=escape(item.title),
                context=escape(item.context),
                status=status_badge("READY_FOR_REVIEW"),
                blockers=blockers,
            )
        )
    queue = "".join(cards)
    if not queue:
        queue = (
            '<section class="empty"><h2>No records are waiting for human review</h2>'
            '<p>Agent-prepared or human-prepared Sources and Facts appear here after submission.</p>'
            '<div class="hero-actions"><a class="button secondary" href="/sources">Browse sources</a>'
            '<a class="button secondary" href="/facts">Browse facts</a></div></section>'
        )
    body = (
        '<section class="hero"><div><p class="eyebrow">Typed review workbench</p>'
        '<h1>Review engineering claims, not generic records</h1>'
        '<p>The queue joins Source revision, typed Fact state, entity identity, conflicts, '
        'missing evidence, and Git change scope before a human takes ownership.</p></div>'
        f'<div class="scope-card"><span>Change scope</span><strong>{escape(overview.change_scope)}</strong>'
        f'<small>{overview.change_count} working-tree changes</small></div></section>'
        '<section class="stats">'
        f'<div><strong>{overview.source_count}</strong><span>Sources</span></div>'
        f'<div><strong>{overview.entity_count}</strong><span>Entities</span></div>'
        f'<div><strong>{overview.fact_count}</strong><span>Facts</span></div>'
        f'<div><strong>{overview.conflict_count}</strong><span>Conflicts</span></div>'
        '</section>'
        '<div class="section-heading workbench-heading"><div><p class="eyebrow">Human queue</p>'
        f'<h2>{len(overview.review_items)} items ready for review</h2></div>'
        '<p>P0.3a exposes typed closure and navigation. Fact approval/rejection is completed in P0.3c.</p></div>'
        f'<section class="review-grid">{queue}</section>'
    )
    return page(
        "Review",
        body,
        workspace=workspace,
        change_count=overview.change_count,
        active="review",
    )


def render_source_list(
    sources: tuple[SourceView, ...],
    *,
    workspace: Path,
    change_count: int,
    selected_status: str | None,
) -> str:
    statuses = ("DRAFT", "READY_FOR_REVIEW", "APPROVED", "REJECTED")
    filters = [
        (
            '<a class="filter selected" href="/sources">All</a>'
            if selected_status is None
            else '<a class="filter" href="/sources">All</a>'
        )
    ]
    for status in statuses:
        css = "filter selected" if selected_status == status else "filter"
        filters.append(
            f'<a class="{css}" href="/sources?status={status}">{escape(status_label(status))}</a>'
        )
    cards = "".join(
        (
            f'<a class="record-card" href="/sources/{escape(source.id)}">'
            '<div class="record-card-top"><div>'
            f'<p class="record-origin">{escape(source.source_type)} · {escape(source.prepared_by)}</p>'
            f'<h3>{escape(source.display_title)}</h3></div>{status_badge(source.status)}</div>'
            f'<p class="record-meta">{escape(source.document_number or "No document number")} · '
            f'{escape(source.revision or "Revision unknown")}</p>'
            '<div class="badges">'
            + (
                "".join(badge(f"Missing {field}", "missing") for field in source.missing_fields)
                if source.missing_fields
                else badge("Required source fields complete", "complete")
            )
            + "</div></a>"
        )
        for source in sources
    )
    if not cards:
        cards = (
            '<section class="empty"><h2>No matching sources</h2>'
            '<p>Create a human draft here or let an Agent prepare one in the selected workspace.</p></section>'
        )
    body = (
        '<div class="page-heading"><div><p class="eyebrow">Typed authority</p>'
        '<h1>Sources</h1><p>Each Source is one exact engineering document revision with '
        'license policy and content-addressed evidence.</p></div>'
        '<a class="button primary" href="/sources/new">New source</a></div>'
        f'<div class="filters">{"".join(filters)}</div>'
        f'<section class="record-grid">{cards}</section>'
    )
    return page(
        "Sources",
        body,
        workspace=workspace,
        change_count=change_count,
        active="sources",
    )


def _text_field(label: str, name: str, value: str | None, *, placeholder: str = "") -> str:
    return (
        '<label class="field">'
        f"<span>{escape(label)}</span>"
        f'<input name="{escape(name)}" value="{escape(value)}" placeholder="{escape(placeholder)}">'
        "</label>"
    )


def _textarea(label: str, name: str, value: str | None, *, placeholder: str = "") -> str:
    return (
        '<label class="field field-wide">'
        f"<span>{escape(label)}</span>"
        f'<textarea name="{escape(name)}" placeholder="{escape(placeholder)}">'
        f"{escape(value)}</textarea></label>"
    )


def _license_select(selected: str) -> str:
    options = "".join(
        (
            f'<option value="{escape(value)}"'
            f'{" selected" if value == selected else ""}>'
            f"{escape(label)}</option>"
        )
        for value, label in LICENSE_LABELS.items()
    )
    return (
        '<label class="field"><span>License class</span>'
        f'<select name="license_class">{options}</select></label>'
    )


def source_form(
    source: SourceView | None,
    *,
    csrf_token: str,
    action: str,
    submit_label: str,
) -> str:
    expected_revision = "" if source is None else source.revision_token
    selected_license = "UNKNOWN" if source is None else source.license_class
    evidence = ""
    if source is not None and source.evidence_sha256 is not None:
        evidence = (
            '<div class="evidence-current"><strong>Current original</strong>'
            f'<a href="/sources/{escape(source.id)}/evidence" target="_blank" rel="noreferrer">'
            f"{escape(source.evidence_sha256)}</a>"
            f"<span>{source.evidence_byte_size} bytes</span></div>"
        )
    return (
        f'<form class="record-form" action="{escape(action)}" method="post" '
        'enctype="multipart/form-data">'
        f"{hidden('csrf_token', csrf_token)}"
        f"{hidden('expected_revision', expected_revision)}"
        '<section class="panel"><div class="section-heading"><div>'
        '<p class="eyebrow">Source identity</p><h2>Enter only confirmed information</h2>'
        '</div><p>Unknown values stay explicit and are checked again before approval.</p></div>'
        '<div class="form-grid">'
        f'{_text_field("Title", "title", None if source is None else source.title, placeholder="Example: TPS5430 datasheet")}'
        f'{_text_field("Document number (optional)", "document_number", None if source is None else source.document_number)}'
        f'{_text_field("Version / revision", "revision", None if source is None else source.revision, placeholder="Example: Rev. G")}'
        f'{_text_field("Source publisher", "source_publisher", None if source is None else source.publisher)}'
        f'{_text_field("Source URL or locator", "source_locator", None if source is None else source.locator)}'
        f"{_license_select(selected_license)}"
        f'{_textarea("License note", "license_note", None if source is None else source.license_note)}'
        f'{_textarea("Preparation note", "preparation_note", None if source is None else source.preparation_note, placeholder="Notes for an Agent or reviewer")}'
        f'{_text_field("Superseded source ID (optional)", "supersedes", None if source is None or source.supersedes is None else source.supersedes.id)}'
        '<label class="field field-wide"><span>PDF original (maximum 64 MiB)</span>'
        '<input name="pdf" type="file" accept="application/pdf,.pdf"></label>'
        f"{evidence}</div></section>"
        '<div class="form-actions"><button class="button primary" type="submit">'
        f"{escape(submit_label)}</button></div></form>"
    )


def _source_details(source: SourceView) -> str:
    original = "Not provided"
    if source.evidence_sha256 is not None:
        original = (
            f'<a href="/sources/{escape(source.id)}/evidence" target="_blank" rel="noreferrer">'
            f"Open PDF · {escape(source.evidence_sha256)}</a>"
        )
    rows = (
        ("Source type", source.source_type),
        ("Document number", source.document_number or "Unknown"),
        ("Revision", source.revision or "Unknown"),
        ("Publisher", source.publisher or "Unknown"),
        ("Source locator", source.locator or "Unknown"),
        ("License", source.license_class),
        ("Original", original),
    )
    rendered = "".join(
        (
            "<div>"
            f"<dt>{escape(label)}</dt>"
            f"<dd>{value if label == 'Original' else escape(value)}</dd>"
            "</div>"
        )
        for label, value in rows
    )
    return (
        f'<section class="panel"><dl class="record-details">{rendered}</dl>'
        f'<div class="note"><strong>Preparation note</strong><p>{escape(source.preparation_note or "None")}</p></div></section>'
    )


def _relationships(
    *,
    supersedes: LinkView | None,
    successors: tuple[LinkView, ...],
    facts: tuple[LinkView, ...],
) -> str:
    predecessor = () if supersedes is None else (supersedes,)
    return (
        '<section class="panel relation-panel"><div><h2>Relationships</h2>'
        '<p class="muted">Navigation is derived from typed authority; no sidecar graph is stored.</p></div>'
        '<div class="relation-group"><h3>Supersedes</h3>'
        f"{link_list(predecessor)}</div>"
        '<div class="relation-group"><h3>Superseded by</h3>'
        f"{link_list(successors)}</div>"
        '<div class="relation-group"><h3>Referenced by Facts</h3>'
        f"{link_list(facts)}</div></section>"
    )


def render_source_detail(
    source: SourceView,
    *,
    workspace: Path,
    change_count: int,
    csrf_token: str,
) -> str:
    missing = (
        "".join(badge(f"Missing {field}", "missing") for field in source.missing_fields)
        if source.missing_fields
        else badge("Required source fields complete", "complete")
    )
    heading = (
        '<div class="page-heading"><div>'
        f'<p class="eyebrow">{escape(source.source_type)} · {escape(source.prepared_by)}</p>'
        f"<h1>{escape(source.display_title)}</h1>"
        f'<p><code>{escape(source.id)}</code> · exact revision and evidence identity</p></div>'
        f'<div class="heading-actions">{status_badge(source.status)}'
        '<a class="button secondary" href="/sources">Back to sources</a></div></div>'
        f'<div class="badges record-missing">{missing}</div>'
    )
    if source.status in {"DRAFT", "REJECTED"}:
        if source.status == "REJECTED" and source.review_history:
            heading += (
                '<div class="notice warning"><strong>Previous review rejected this source</strong>'
                f"<p>{escape(source.review_history[-1].comment or 'No comment')}</p></div>"
            )
        content = source_form(
            source,
            csrf_token=csrf_token,
            action=f"/sources/{source.id}/save",
            submit_label="Save draft",
        )
        content += (
            f'<form class="inline-action" action="/sources/{escape(source.id)}/submit" method="post">'
            f"{hidden('csrf_token', csrf_token)}{hidden('expected_revision', source.revision_token)}"
            '<div><strong>Ready for human review?</strong>'
            '<p>Submission freezes the Source until a reviewer approves or rejects it.</p></div>'
            '<button class="button primary" type="submit">Submit source</button></form>'
        )
    elif source.status == "READY_FOR_REVIEW":
        content = _source_details(source)
        content += (
            '<section class="panel review-panel"><p class="eyebrow">Human decision</p>'
            '<h2>Verify Source revision, license, and PDF original</h2>'
            '<p>Source review remains available while P0.3a adds typed workbench navigation.</p>'
            f'<form action="/sources/{escape(source.id)}/approve" method="post">'
            f"{hidden('csrf_token', csrf_token)}{hidden('expected_revision', source.revision_token)}"
            '<label class="field field-wide"><span>Approval note (optional)</span>'
            '<textarea name="review_comment"></textarea></label>'
            '<button class="button primary" type="submit">Approve source</button></form>'
            f'<form action="/sources/{escape(source.id)}/reject" method="post">'
            f"{hidden('csrf_token', csrf_token)}{hidden('expected_revision', source.revision_token)}"
            '<label class="field field-wide"><span>Rejection reason (required)</span>'
            '<textarea name="review_comment" required></textarea></label>'
            '<button class="button danger" type="submit">Reject for revision</button></form></section>'
        )
    else:
        content = (
            '<div class="notice success"><strong>This Source is approved and immutable in place</strong>'
            '<p>Corrections require a new Source revision with an explicit supersedes relation.</p></div>'
            + _source_details(source)
        )
    content += _relationships(
        supersedes=source.supersedes,
        successors=source.successors,
        facts=source.facts,
    )
    content += (
        '<section class="panel"><h2>Review history</h2>'
        f"{review_history(source.review_history)}</section>"
    )
    return page(
        source.display_title,
        heading + content,
        workspace=workspace,
        change_count=change_count,
        active="sources",
    )


def render_new_source(
    *, workspace: Path, change_count: int, csrf_token: str
) -> str:
    body = (
        '<div class="page-heading"><div><p class="eyebrow">New Source</p>'
        '<h1>Create one exact document revision</h1>'
        '<p>The form writes only the selected knowledge workspace and never stages Git.</p></div>'
        '<a class="button secondary" href="/sources">Back to sources</a></div>'
        + source_form(
            None,
            csrf_token=csrf_token,
            action="/sources/new",
            submit_label="Save new draft",
        )
    )
    return page(
        "New source",
        body,
        workspace=workspace,
        change_count=change_count,
        active="sources",
    )


def render_entity_list(
    entities: tuple[EntityView, ...],
    *,
    workspace: Path,
    change_count: int,
    selected_kind: str | None,
) -> str:
    kinds = ("MANUFACTURER", "COMPONENT", "PACKAGE")
    filters = [
        (
            '<a class="filter selected" href="/entities">All</a>'
            if selected_kind is None
            else '<a class="filter" href="/entities">All</a>'
        )
    ]
    for kind in kinds:
        css = "filter selected" if selected_kind == kind else "filter"
        filters.append(
            f'<a class="{css}" href="/entities?kind={kind}">{escape(status_label(kind))}</a>'
        )
    cards = "".join(
        (
            f'<a class="record-card" href="/entities/{escape(entity.id)}">'
            '<div class="record-card-top"><div>'
            f'<p class="record-origin">{escape(entity.kind)} · {escape(entity.prepared_by)}</p>'
            f'<h3>{escape(entity.label)}</h3></div>{badge("Exact identity", "complete")}</div>'
            f'<p class="record-meta">{escape(entity.normalized_identity)}</p>'
            f'<div class="badges">{badge(f"{len(entity.facts)} linked facts")}</div></a>'
        )
        for entity in entities
    )
    if not cards:
        cards = '<section class="empty"><h2>No matching entities</h2><p>Entities are created by the typed Agent workflow.</p></section>'
    body = (
        '<div class="page-heading"><div><p class="eyebrow">Exact identity</p>'
        '<h1>Entities</h1><p>Manufacturer, Component, and Package identities are separate typed records. '
        'The workbench never infers package or revision from an MPN suffix.</p></div></div>'
        f'<div class="filters">{"".join(filters)}</div>'
        f'<section class="record-grid">{cards}</section>'
    )
    return page(
        "Entities",
        body,
        workspace=workspace,
        change_count=change_count,
        active="entities",
    )


def render_entity_detail(
    entity: EntityView, *, workspace: Path, change_count: int
) -> str:
    rows = (
        ("Kind", entity.kind),
        ("Normalized identity", entity.normalized_identity),
        ("Prepared by", entity.prepared_by),
        ("Family", entity.family or "None"),
        ("Note", entity.note or "None"),
    )
    detail_rows = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
        for label, value in rows
    )
    manufacturer = () if entity.manufacturer is None else (entity.manufacturer,)
    body = (
        '<div class="page-heading"><div><p class="eyebrow">Typed Entity</p>'
        f"<h1>{escape(entity.label)}</h1><p><code>{escape(entity.id)}</code></p></div>"
        '<a class="button secondary" href="/entities">Back to entities</a></div>'
        f'<section class="panel"><dl class="record-details">{detail_rows}</dl></section>'
        '<section class="panel relation-panel"><div><h2>Relationships</h2>'
        '<p class="muted">References are resolved by exact stable IDs.</p></div>'
        '<div class="relation-group"><h3>Manufacturer</h3>'
        f"{link_list(manufacturer)}</div>"
        '<div class="relation-group"><h3>Related entities</h3>'
        f"{link_list(entity.related_entities)}</div>"
        '<div class="relation-group"><h3>Facts</h3>'
        f"{link_list(entity.facts)}</div></section>"
    )
    return page(
        entity.label,
        body,
        workspace=workspace,
        change_count=change_count,
        active="entities",
    )


def render_fact_list(
    facts: tuple[FactView, ...],
    *,
    workspace: Path,
    change_count: int,
    selected_status: str | None,
) -> str:
    statuses = ("DRAFT", "READY_FOR_REVIEW", "APPROVED", "REJECTED")
    filters = [
        (
            '<a class="filter selected" href="/facts">All</a>'
            if selected_status is None
            else '<a class="filter" href="/facts">All</a>'
        )
    ]
    for status in statuses:
        css = "filter selected" if selected_status == status else "filter"
        filters.append(
            f'<a class="{css}" href="/facts?status={status}">{escape(status_label(status))}</a>'
        )
    cards = "".join(
        (
            f'<a class="record-card" href="/facts/{escape(fact.id)}">'
            '<div class="record-card-top"><div>'
            f'<p class="record-origin">{escape(fact.fact_type)} · {escape(fact.prepared_by)}</p>'
            f'<h3>{escape(fact.title)}</h3></div>{status_badge(fact.status)}</div>'
            f'<p class="record-meta">{escape(", ".join(fact.applicability) or "General applicability")}</p>'
            '<div class="badges">'
            + (
                "".join(badge(value, "missing") for value in fact.blockers)
                if fact.blockers
                else badge("Typed closure ready", "complete")
            )
            + "</div></a>"
        )
        for fact in facts
    )
    if not cards:
        cards = '<section class="empty"><h2>No matching facts</h2><p>Typed engineering facts are created by the Agent ingestion workflow.</p></section>'
    body = (
        '<div class="page-heading"><div><p class="eyebrow">Engineering claims</p>'
        '<h1>Facts</h1><p>Facts keep typed payload, applicability, Source anchors, review history, '
        'and semantic conflict state together.</p></div></div>'
        f'<div class="filters">{"".join(filters)}</div>'
        f'<section class="record-grid">{cards}</section>'
    )
    return page(
        "Facts",
        body,
        workspace=workspace,
        change_count=change_count,
        active="facts",
    )


def _anchor_cards(fact: FactView) -> str:
    if not fact.anchors:
        return '<p class="muted">No evidence anchors.</p>'
    cards = []
    for anchor in fact.anchors:
        bbox = (
            "Missing"
            if anchor.bbox is None
            else ", ".join(f"{value:.4f}" for value in anchor.bbox)
        )
        cards.append(
            '<article class="anchor-card">'
            '<div class="anchor-heading">'
            f'<a href="{escape(anchor.source.href)}">{escape(anchor.source.label)}</a>'
            f"{badge('Complete anchor', 'complete') if anchor.complete else badge('Incomplete anchor', 'missing')}"
            "</div>"
            f"<dl><div><dt>Page</dt><dd>{anchor.page}</dd></div>"
            f"<div><dt>Normalized bbox</dt><dd><code>{escape(bbox)}</code></dd></div></dl>"
            f'<blockquote>{escape(anchor.quote or "Quote missing")}</blockquote>'
            f'<p class="hash">quote_sha256: {escape(anchor.quote_sha256 or "missing")}</p>'
            "</article>"
        )
    return "".join(cards)


def render_fact_detail(
    fact: FactView, *, workspace: Path, change_count: int
) -> str:
    blockers = (
        "".join(badge(value, "missing") for value in fact.blockers)
        if fact.blockers
        else badge("No current closure blocker", "complete")
    )
    payload = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
        for label, value in fact.payload_rows
    )
    predecessor = () if fact.supersedes is None else (fact.supersedes,)
    body = (
        '<div class="page-heading"><div>'
        f'<p class="eyebrow">{escape(fact.fact_type)} · {escape(fact.prepared_by)}</p>'
        f"<h1>{escape(fact.title)}</h1><p><code>{escape(fact.id)}</code></p></div>"
        f'<div class="heading-actions">{status_badge(fact.status)}'
        '<a class="button secondary" href="/facts">Back to facts</a></div></div>'
        f'<div class="badges record-missing">{blockers}</div>'
        '<section class="typed-layout"><section class="panel"><h2>Typed payload</h2>'
        f'<dl class="record-details">{payload}</dl>'
        '<div class="typed-list"><h3>Conditions</h3>'
        f'<p>{escape(" · ".join(fact.conditions) or "None")}</p>'
        '<h3>Applicability</h3>'
        f'<p>{escape(" · ".join(fact.applicability) or "None")}</p></div></section>'
        '<section class="panel"><h2>Entity identity</h2>'
        f'<div class="relation-stack">{link_list(fact.entities)}</div>'
        '<h2>Source revisions</h2>'
        f'<div class="relation-stack">{link_list(fact.sources)}</div></section></section>'
        '<section class="panel"><div class="section-heading"><div><p class="eyebrow">Evidence anchors</p>'
        f'<h2>{len(fact.anchors)} anchors</h2></div>'
        '<p>P0.3a exposes anchor identity and quote data. Visual PDF page/bbox rendering is P0.3b.</p></div>'
        f'<div class="anchor-grid">{_anchor_cards(fact)}</div></section>'
        '<section class="panel relation-panel"><div><h2>Fact relationships</h2>'
        '<p class="muted">Conflicts and supersedes remain explicit; the UI does not choose a winner.</p></div>'
        '<div class="relation-group"><h3>Conflicts</h3>'
        f"{link_list(fact.conflicts)}</div>"
        '<div class="relation-group"><h3>Supersedes</h3>'
        f"{link_list(predecessor)}</div>"
        '<div class="relation-group"><h3>Superseded by</h3>'
        f"{link_list(fact.successors)}</div></section>"
        '<section class="panel"><h2>Review history</h2>'
        f"{review_history(fact.review_history)}</section>"
    )
    return page(
        fact.title,
        body,
        workspace=workspace,
        change_count=change_count,
        active="facts",
    )


def render_diff(
    *,
    status_text: str,
    diff_text: str,
    workspace: Path,
    change_count: int,
) -> str:
    body = (
        '<div class="page-heading"><div><p class="eyebrow">Pre-publication check</p>'
        '<h1>Repository changes</h1><p>This view is read-only and never runs add, commit, or push.</p></div>'
        '<a class="button secondary" href="/review">Back to review</a></div>'
        '<section class="panel diff-panel"><h2>Git status</h2>'
        f"<pre>{escape(status_text)}</pre><h2>Content diff and new-file preview</h2>"
        f"<pre>{escape(diff_text)}</pre></section>"
    )
    return page(
        "Repository changes",
        body,
        workspace=workspace,
        change_count=change_count,
        active="diff",
    )


def render_error(
    *,
    status_code: int,
    status_phrase: str,
    message: str,
    workspace: Path,
    change_count: int,
) -> str:
    body = (
        '<section class="error-page"><p class="eyebrow">Operation not completed</p>'
        f"<h1>{status_code} · {escape(status_phrase)}</h1>"
        f"<p>{escape(message)}</p>"
        '<a class="button primary" href="/review">Back to review</a></section>'
    )
    return page(
        "Operation not completed",
        body,
        workspace=workspace,
        change_count=change_count,
        active="",
    )
