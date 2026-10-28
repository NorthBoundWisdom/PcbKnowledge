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
