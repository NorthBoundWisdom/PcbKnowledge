"""Pure HTML rendering for P0.3c review-decision closure."""

from __future__ import annotations

import html

from pcbknowledge.git_native.review_closure import ReviewDecisionView


VISUAL_EVIDENCE_SLOT = '<div id="visual-evidence-review-slot"></div>'


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _hidden(name: str, value: str) -> str:
    return f'<input type="hidden" name="{_escape(name)}" value="{_escape(value)}">'


def _badge(label: str, tone: str = "") -> str:
    css = f"badge {tone}".strip()
    return f'<span class="{_escape(css)}">{_escape(label)}</span>'


def render_review_decision_panel(
    decision: ReviewDecisionView,
    *,
    csrf_token: str,
    expected_revision: str,
    approve_action: str,
    reject_action: str,
    subject_label: str,
) -> str:
    """Render decision gates, exact closure diff, and guarded human actions."""

    scope_tone = "complete" if decision.scope_blocker is None else "missing"
    approval_gates = (
        "".join(_badge(value, "missing") for value in decision.approval_blockers)
        if decision.approval_blockers
        else _badge("Approval closure satisfied", "complete")
    )
    decision_gates = (
        "".join(_badge(value, "missing") for value in decision.decision_blockers)
        if decision.decision_blockers
        else _badge("Decision scope satisfied", "complete")
    )
    selected_paths = "".join(
        f"<li><code>{_escape(path)}</code></li>" for path in decision.selected.paths
    ) or "<li>None</li>"
    selected_status = (
        "\n".join(decision.selected.status_lines)
        or "No selected closure paths are currently changed."
    )

    if decision.can_approve:
        approve = (
            f'<form action="{_escape(approve_action)}" method="post">'
            f"{_hidden('csrf_token', csrf_token)}"
            f"{_hidden('expected_revision', expected_revision)}"
            '<label class="field field-wide"><span>Approval note (optional)</span>'
            '<textarea name="review_comment"></textarea></label>'
            f'<button class="button primary" type="submit">Approve {_escape(subject_label)}</button></form>'
        )
    else:
        approve = (
            '<div class="decision-disabled"><strong>Approval blocked</strong>'
            '<p>Resolve every approval and decision gate before approval.</p>'
            '<button class="button primary" type="button" disabled>Approval blocked</button></div>'
        )

    if decision.can_reject:
        reject = (
            f'<form action="{_escape(reject_action)}" method="post">'
            f"{_hidden('csrf_token', csrf_token)}"
            f"{_hidden('expected_revision', expected_revision)}"
            '<label class="field field-wide"><span>Rejection reason (required)</span>'
            '<textarea name="review_comment" required></textarea></label>'
            f'<button class="button danger" type="submit">Reject {_escape(subject_label)}</button></form>'
        )
    else:
        reject = (
            '<div class="decision-disabled"><strong>Rejection blocked</strong>'
            '<p>Resolve the decision-scope gate before mutating review history.</p>'
            '<button class="button danger" type="button" disabled>Rejection blocked</button></div>'
        )

    return (
        '<section class="panel review-closure-panel">'
        '<div class="section-heading"><div><p class="eyebrow">Human decision closure</p>'
        '<h2>Review the exact closure and next-commit scope</h2></div>'
        '<p>Buttons are only a projection. The application recomputes all gates again immediately before writing authority.</p></div>'
        '<div class="decision-scope">'
        f'<span>Next-commit candidate</span>{_badge(decision.change_scope, scope_tone)}</div>'
        '<div class="decision-gates"><div><h3>Decision gates</h3>'
        f'<div class="badges">{decision_gates}</div></div>'
        '<div><h3>Approval-only gates</h3>'
        f'<div class="badges">{approval_gates}</div></div></div>'
        '<details class="selected-closure" open><summary>Selected closure</summary>'
        f'<ul>{selected_paths}</ul><h3>Selected Git status</h3><pre>{_escape(selected_status)}</pre>'
        f'<h3>Selected diff</h3><pre>{_escape(decision.selected.diff_text)}</pre></details>'
        f'<div class="review-decision-actions">{approve}{reject}</div></section>'
    )
