"""Pure escaped HTML for noncanonical intake candidates, never approval controls."""
from __future__ import annotations

import json
from urllib.parse import urlencode

from pcbknowledge.git_native.intake_workbench import FILTERS, IntakeBrowseView
from pcbknowledge.git_native.intake_reference import IntakeReference
from pcbknowledge.git_native.workbench_views import escape, page


def render_intake(view: IntakeBrowseView, *, change_count: int) -> str:
    fields = "".join(
        f'<label>{escape(name)} <input name="{escape(name)}" '
        f'value="{escape(view.filters.get(name, ""))}"></label>' for name in FILTERS)
    options = "".join(f'<option value="{mode}"' + (' selected' if mode == view.mode else '')
                      + f'>{label}</option>' for mode, label in (("facts", "Facts"), ("issues", "Source issues")))
    body = f'''<section><h1>Curated intake · read only</h1>
<p><strong>NONCANONICAL · NOT_LOCALLY_VERIFIED</strong></p>
<p>These are working-tree candidates, not published canonical Facts. Recorded Agent
review is not human approval or local verification of original documents.
Search hits are not engineering conclusions or circuit qualification.</p>
<form method="get" action="/intake"><label>Mode <select name="mode">{options}</select></label>
<label>Text query <input name="q" value="{escape(view.query)}"></label>{fields}
<button type="submit">Search intake</button></form>
<p>Structured filters are exact and case-sensitive; blank fields mean no filter.
Text terms use case-insensitive AND matching. Kind and parameter apply only to facts.
Switching to issues requires clearing those fact filters. No match does not prove
compatibility, safety or absence of uncertainty.</p>
<p>{view.total_count} candidates · page {view.page_number} of {view.page_count} · up to 25 per page</p></section>'''
    for candidate, context_digest in zip(view.candidates, view.candidate_digests):
        record = candidate.get("fact", candidate.get("source_issue", {}))
        source = candidate["source"]
        payload = json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        warning_count = len(candidate.get("source_issues", []))
        disposition_count = len(candidate.get("source_issue_dispositions", []))
        if view.mode == "facts":
            summary = (f'<p><strong>{escape(record.get("parameter", "Unknown parameter"))}</strong>: '
                       f'{escape(json.dumps(record.get("value"), ensure_ascii=False))} '
                       f'{escape(record.get("unit") or "")}</p>'
                       f'<p>Conditions: {escape(record.get("conditions", "Not recorded"))}</p>'
                       f'<p>{warning_count} same-source warnings; {disposition_count} linked dispositions. '
                       'Inspect complete evidence before using this candidate.</p>')
        else:
            summary = (f'<p><strong>{escape(record.get("issue_status", "Unknown status"))}</strong></p>'
                       f'<p>{escape(record.get("description", "Not recorded"))}</p>'
                       f'<p>{disposition_count} linked dispositions; original issue remains visible.</p>')
        item_query = urlencode({"batch": candidate["path"], "id": record["id"],
                                "sha256": view.batch_digests[candidate["path"]], "context": context_digest,
                                "type": "fact" if view.mode == "facts" else "issue"})
        body += (f'<article><h2>{escape(record.get("id", "Candidate"))}</h2>'
                 f'<p>{escape(source.get("manufacturer", "Unknown manufacturer"))} · '
                 f'{escape(source.get("device", "Unknown device"))} · '
                 f'{escape(source.get("package", "Unknown package"))}</p>'
                 f'<p>Batch: <code>{escape(candidate["path"])}</code> · '
                 f'{escape(candidate["acceptance_status"])}</p>'
                 + f'<p><a href="/intake/item?{escape(item_query)}">Open exact pinned item</a></p>'
                 + summary + '<details><summary>Complete evidence and warnings</summary>'
                 '<p>Complete candidate payload: source revision and evidence, fact/issue '
                 'conditions, same-source warnings and linked dispositions are preserved below. '
                 'Source URLs are displayed as text; this page does not fetch originals.</p>'
                 f'<pre>{escape(payload)}</pre></details></article>')
    if not view.candidates:
        body += '<p>No matching candidates in the selected workspace. No source-checkout fallback is used.</p>'
    links = []
    for number, label in ((view.page_number - 1, "Previous"), (view.page_number + 1, "Next")):
        if 1 <= number <= view.page_count:
            query = urlencode({"mode": view.mode, "q": view.query, **view.filters, "page": number})
            links.append(f'<a href="/intake?{escape(query)}">{label}</a>')
    body += '<nav aria-label="Intake result pages">' + ' '.join(links) + '</nav>'
    return page("Curated intake", body, workspace=view.workspace, change_count=change_count, active="intake")


def render_intake_item(view: IntakeReference, *, change_count: int) -> str:
    candidate = view.candidate
    record = candidate["fact" if view.record_type == "fact" else "source_issue"]
    payload = json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    body = (f'<section><h1>{escape(record["id"])}</h1>'
            '<p><strong>NONCANONICAL · NOT_LOCALLY_VERIFIED · READ ONLY</strong></p>'
            f'<p>Exact {escape(view.record_type)} in <code>{escape(candidate["path"])}</code></p>'
            f'<p>Batch JSON SHA-256: <code>{escape(view.batch_sha256)}</code></p>'
            f'<p>Candidate context SHA-256: <code>{escape(view.context_sha256)}</code></p>'
            '<p>This local link verifies the selected working-tree batch JSON bytes, not a '
            'canonical published snapshot or original PDF. It is meaningful only in the '
            'selected workspace. Agent review is not human approval or circuit qualification.</p>'
            '<p>The context digest also pins the complete candidate projection and linked disposition '
            'receipts, including their own paths and hashes. Changed metadata expires the link; '
            'neither digest verifies original documents. A conservative disposition does not '
            'erase original warnings.</p>'
            '<p><a href="/intake">Return to intake browse</a></p>'
            '<h2>Complete candidate, source conditions and warnings</h2>'
            f'<pre>{escape(payload)}</pre></section>')
    return page("Pinned intake item", body, workspace=view.workspace,
                change_count=change_count, active="intake")
