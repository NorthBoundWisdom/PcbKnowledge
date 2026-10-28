# Read-only curated intake workbench

The local workbench's **Curated intake** navigation opens `GET /intake` for the
explicitly selected knowledge workspace. It exposes the same noncanonical
working-tree candidates as `intake search` and `intake issues`; it does not replace
canonical Facts or silently fall back to the software checkout. Starting the
existing local runtime remains an explicit operation; no new listener or hosted
service is introduced.

The default view lists fact candidates. Choose **Source issues** to search warnings
even when no fact matches the text query. Structured `source_id`, `manufacturer`,
`device`, `package`, `kind` and `parameter` filters use exact strings, preserving
case, Unicode and whitespace. Blank controls mean no filter. `kind` and `parameter`
are fact-only; clear them before changing to issue mode. Text `q` uses the existing
case-insensitive AND lexical search, not an electrical reasoning engine.

Results show 25 candidates per page, the total count, page number and previous/next
links preserving filters. Readable fact values/conditions or issue descriptions and warning/disposition counts
are visible first. Native expandable details retain complete escaped candidate JSON, including
source revision, fact/issue conditions, evidence anchors, same-source warnings,
recorded provenance and linked dispositions supplied by the existing reader.
This is the complete search projection, not a full batch export or fresh source
review. URLs are displayed as inert text; the page neither downloads nor renders
original source documents. No result proves compatibility, safety, absence of
uncertainty or circuit qualification.

The page prominently retains **NONCANONICAL** and **NOT_LOCALLY_VERIFIED**. Agent
review does not become human approval; a conservative disposition does not erase
original unresolved wording. There are no approval, edit, upload, Git publication
or evidence-download controls and no `/intake` mutation route. Existing loopback
Host checks and response security headers apply. Unknown or duplicate parameters,
malformed encoding, unsupported issue-mode filters, control characters, oversized
queries, invalid page numbers and invalid intake metadata produce HTTP 400 rather
than permissive fallback. Text fields are limited to 512 characters, query strings
to 8192 characters and page numbers to six positive decimal digits.

## Manual acceptance

1. Start the existing local runtime with an explicit workspace, then open
   `http://127.0.0.1:18080/intake` (or its explicitly configured port).
2. Confirm the selected workspace path is visible. An empty external workspace
   must show no candidates rather than the software checkout's curated collection.
3. Filter by an exact device/source and inspect the complete source, conditions,
   warnings and evidence payload. Compare it with the corresponding CLI query.
4. Switch to source issues after clearing fact-only filters. Confirm warnings can
   be found independently of fact text. Check the previous/next links on a large
   result set and confirm filters remain intact.
5. Confirm no approval/edit/upload/download action exists and a no-match result
   does not claim safety. A duplicate filter URL must return an error page.

Implementation checks include actual loopback HTTP smoke tests for both the base
server and documented workspace-aware runtime against a temporary
external workspace, complete JSON round-trip escaping, exact filter behavior,
pagination without candidate loss, warning/disposition preservation, malformed input,
metadata errors and rejected POST with unchanged intake bytes. They do not substitute
for visual browser review or original-document verification.

Independent Agent review on 2026-10-28 by
`agent:/root/check_and_resume_knowledge/review_resistor_eval` passed all nine
focused tests and an additional actual workspace-server HTTP check with 51
candidates across three pages, complete payload/filter preservation and nine
malformed-query rejections. The documented workspace-server entry point was
explicitly verified after its intake initialization was repaired. Author:
`agent:/root/check_and_resume_knowledge/implement_resistor_boundary_eval`.
Browser visual review was not completed: the available Chromium process could
not start in the execution environment. HTTP behavior is verified, not visual
layout. The manual acceptance steps above remain applicable.

## Exact local item links

Each browse result now provides **Open exact pinned item**, a read-only
`GET /intake/item` URL. Its required selectors are `batch` (normalized
`knowledge/intake/...json` path), batch-local `id`, `type` (`fact` or `issue`),
`sha256` (batch JSON bytes) and `context` (the complete candidate projection).
The context is SHA-256 of UTF-8 JSON with sorted keys, unescaped Unicode,
no NaN and compact comma/colon separators. It includes linked disposition
receipt paths and hashes, so changing a disposition alone expires the old link.
It is a local review reference, not a canonical publication or PDF-verification
receipt; it works only in a workspace containing the same relevant metadata.

Browse labels and both digests come from one validated loader result. Opening a
link resolves the exact record type and ID only inside its selected batch; a
same-named record in another batch cannot substitute. Invalid/duplicate selectors
or unsafe path spelling return HTTP 400, missing batches/records return 404, and
changed batch bytes or context return 409 with a stale-link explanation. It never
silently refreshes the pin or redirects to a newer record. Return to browse and
review newly displayed evidence before using a replacement link.

The detail page retains the full escaped search projection: source, record,
conditions, record evidence, same-source warnings for facts, and applicable linked
dispositions. Issue detail retains its complete selected issue and disposition
context. It does not pretend to export the whole batch or unrelated warnings.
No direct path supplied by the URL is opened: resolution uses only validated
intake-loader results. The same selected-workspace and no-mutation rules apply.

Manual check: open a result in another tab, confirm batch and context hashes, then
modify a disposable synthetic batch or linked disposition and reload its old URL.
Expect a stale-link error, never a newly substituted answer. Test this only in a
disposable workspace, not by changing accepted knowledge as an experiment.

Exact-link independent Agent review on 2026-10-28 by
`agent:/root/check_and_resume_knowledge/review_resistor_eval` passed 25 focused
tests and full-payload parity for 14 pre-change/current search and issue queries.
An actual workspace-server check followed seven MCP23017 fact links, preserving
their full warnings and dispositions; changing only disposition bytes invalidated
all seven old links with HTTP 409 while new browsing remained available. This is
HTTP/data validation, not browser visual or original-PDF verification.

## Agent CLI references without a running server

The Agent CLI uses the same pure reference resolver as `/intake/item`. First
**capture current metadata** for a known exact batch-local record:

```bash
python3 configs/pcbknowledge_agent.py --repo . intake pin \
  --batch knowledge/intake/ads1115-input-interface-constraints.json \
  --id ads1115-app-01 --type fact
```

`pin` does not verify an older reference or approve its contents. Its JSON result
has format `pcbknowledge-intake-reference-v1`, operation
`CAPTURE_CURRENT_METADATA`, a `reference` object containing `batch`, `id`, `type`,
`sha256` and `context`, and the complete `candidate`. Inspect that candidate's
source, conditions, evidence, warnings and any dispositions before reusing its
reference. Both pins and the displayed candidate come from one validated load.

To verify a saved reference later, pass **all five** exact values to `intake item`:

```text
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake item --batch BATCH --id ID --type TYPE --sha256 SHA256 --context CONTEXT
```

The uppercase words above are placeholders for the explicit workspace and values
from the saved `reference`, not defaults or commands to run literally. `TYPE` is
`fact` or `issue`; the same ID in the other type or another batch cannot substitute.
The GUI link's five query selectors have these same names and values. No server,
HTTP request, original PDF, online lookup or new runtime dependency is required.

Successful `item` output uses operation `VERIFY_PINNED_METADATA`, retaining the
same complete candidate and reference. It verifies only current metadata equality,
not canonical publication, original source bytes, human review or engineering
correctness. Both operations retain `canonical: false` and
`evidence_verification: NOT_LOCALLY_VERIFIED`. Issue candidates retain the selected
issue and its disposition context, not a claim to export the entire batch.

Every selector is required exactly once; duplicate, missing, malformed and
unsupported options fail rather than selecting the last value. Missing records
report `INTAKE_ITEM_NOT_FOUND`; changed bytes or candidate/disposition context
report `STALE_INTAKE_REFERENCE`. Failures exit 2 and emit no successful JSON on
stdout. `item` never recaptures, updates or writes a reference. If it is stale,
review new evidence explicitly before deliberately calling `pin` again. Neither
operation writes files or initializes canonical/cache directories, and an empty
selected workspace never falls back to the software checkout's collection.

Independent Agent review on 2026-10-28 by
`agent:/root/resume_knowledge_work/review_pinned_intake_cli` passed 25 focused tests,
actual CLI duplicate/unknown-selector rejections, GUI/CLI reference equivalence,
workspace byte/directory preservation, and seven old/current CLI stdout comparisons.
Author: `agent:/root/resume_knowledge_work/implement_pinned_intake_cli`.
Local Build/Test each passed 378 tests without skips; the unchanged 539 existing
retrieval/disposition cases and metadata-only package passed. These are software
checks, not new source-original, browser-visual or human engineering verification.
