"""Pure HTML renderer for visual PDF evidence review."""

from __future__ import annotations

import html

from pcbknowledge.git_native.evidence_review import (
    EvidenceReviewAnchorView,
    FactEvidenceReviewView,
)


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _number(value: float) -> str:
    return format(value, ".12g")


def _bbox_overlay(anchor: EvidenceReviewAnchorView) -> str:
    if anchor.bbox is None:
        return ""
    x0, y0, x1, y1 = anchor.bbox
    return (
        '<svg class="evidence-bbox-overlay" viewBox="0 0 1 1" '
        'preserveAspectRatio="none" aria-label="Evidence bounding box">'
        f'<rect x="{_number(x0)}" y="{_number(y0)}" '
        f'width="{_number(x1 - x0)}" height="{_number(y1 - y0)}" '
        'vector-effect="non-scaling-stroke"></rect></svg>'
    )


def _render_anchor(
    anchor: EvidenceReviewAnchorView,
    *,
    previous_anchor: EvidenceReviewAnchorView | None,
    next_anchor: EvidenceReviewAnchorView | None,
) -> str:
    status = (
        '<span class="badge complete">Complete anchor</span>'
        if anchor.complete
        else '<span class="badge missing">Incomplete anchor</span>'
    )
    source_meta = (
        f"{_escape(anchor.source_type)} · revision {_escape(anchor.source_revision)} · "
        f"{_escape(anchor.license_class)}"
    )
    bbox = (
        "None"
        if anchor.bbox is None
        else ", ".join(_number(value) for value in anchor.bbox)
    )
    quote = (
        '<p class="muted">No quote is attached to this anchor.</p>'
        if anchor.quote is None
        else f'<blockquote class="evidence-quote">{_escape(anchor.quote)}</blockquote>'
    )
    quote_hash = anchor.quote_sha256 or "None"

    if anchor.evidence_url is None:
        viewer = (
            '<div class="notice warning evidence-policy-block">'
            '<strong>PDF evidence is not exposed by this workbench.</strong>'
            f'<p>{_escape(anchor.blocked_reason or "Evidence is unavailable.")}</p></div>'
        )
    else:
        viewer = (
            f'<div class="evidence-page-stage" data-pdf-review '
            f'data-pdf-url="{_escape(anchor.evidence_url)}" '
            f'data-page="{anchor.page}">'
            '<p class="evidence-render-status" data-render-status>'
            f'Rendering Source page {anchor.page} locally...</p>'
            '<div class="evidence-page-frame" data-page-frame hidden>'
            '<canvas class="evidence-page-canvas" data-pdf-canvas></canvas>'
            f'{_bbox_overlay(anchor)}'
            '</div></div>'
        )

    previous_link = (
        ""
        if previous_anchor is None
        else f'<a href="#{_escape(previous_anchor.anchor_id)}">← Anchor {previous_anchor.index}</a>'
    )
    next_link = (
        ""
        if next_anchor is None
        else f'<a href="#{_escape(next_anchor.anchor_id)}">Anchor {next_anchor.index} →</a>'
    )
    navigation = (
        '<nav class="evidence-card-nav" aria-label="Evidence anchor navigation">'
        f"{previous_link}{next_link}</nav>"
    )

    document_number = (
        ""
        if anchor.source_document_number is None
        else f' · {_escape(anchor.source_document_number)}'
    )
    return (
        f'<article class="evidence-review-card" id="{_escape(anchor.anchor_id)}">'
        '<div class="evidence-card-heading"><div>'
        f'<p class="eyebrow">Anchor {anchor.index}</p>'
        f'<h3><a href="/sources/{_escape(anchor.source_id)}">'
        f'{_escape(anchor.source_label)}</a></h3>'
        f'<p>{source_meta}{document_number}</p></div>{status}</div>'
        f"{viewer}"
        '<div class="evidence-anchor-metadata">'
        f'<div><strong>Page</strong><span>{anchor.page}</span></div>'
        f'<div><strong>Coordinate space</strong><span>{_escape(anchor.coordinate_space)}</span></div>'
        f'<div><strong>Normalized bbox</strong><span>{_escape(bbox)}</span></div>'
        '</div>'
        '<div class="evidence-quote-panel"><strong>Quoted evidence</strong>'
        f'{quote}<p class="hash-line"><span>quote_sha256</span><code>{_escape(quote_hash)}</code></p>'
        '</div>'
        f"{navigation}</article>"
    )


def render_fact_evidence_review(view: FactEvidenceReviewView) -> str:
    """Render a self-contained visual-evidence section for one Fact detail page."""

    context = " · ".join(_escape(item) for item in view.subject_context)
    applicability = (
        ", ".join(_escape(item) for item in view.applicability) or "Not specified"
    )
    conditions = ", ".join(_escape(item) for item in view.conditions) or "Not specified"
    if not view.anchors:
        cards = (
            '<section class="empty evidence-empty"><h3>No evidence anchors</h3>'
            '<p>The Fact remains explicit and cannot be visually reviewed until an anchor is supplied.</p>'
            '</section>'
        )
        anchor_navigation = ""
    else:
        anchor_navigation = (
            '<nav class="evidence-anchor-nav" aria-label="Evidence anchors">'
            + "".join(
                f'<a href="#{_escape(anchor.anchor_id)}">'
                f'Anchor {anchor.index} · p{anchor.page} · {_escape(anchor.source_revision)}</a>'
                for anchor in view.anchors
            )
            + "</nav>"
        )
        rendered: list[str] = []
        for index, anchor in enumerate(view.anchors):
            rendered.append(
                _render_anchor(
                    anchor,
                    previous_anchor=None if index == 0 else view.anchors[index - 1],
                    next_anchor=(
                        None if index + 1 == len(view.anchors) else view.anchors[index + 1]
                    ),
                )
            )
        cards = '<div class="evidence-review-list">' + "".join(rendered) + "</div>"

    return (
        '<section class="panel visual-evidence-review" id="visual-evidence-review">'
        '<div class="section-heading"><div>'
        '<p class="eyebrow">Visual evidence review</p>'
        '<h2>Inspect the exact Source page and normalized anchor</h2>'
        '</div><p>PDF bytes stay local. The canvas is rendered from the selected workspace; '
        'the overlay uses PDF_NORMALIZED_V1 coordinates.</p></div>'
        '<div class="evidence-context">'
        f'<div><strong>Subject</strong><span>{context or "Unknown"}</span></div>'
        f'<div><strong>Applicability</strong><span>{applicability}</span></div>'
        f'<div><strong>Conditions</strong><span>{conditions}</span></div>'
        '</div>'
        f"{anchor_navigation}{cards}</section>"
    )
