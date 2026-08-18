# PcbKnowledge Git-native architecture

> Status: P0.3 Local Review Workbench implementation complete; P0.4a real-data pilot next
> Updated: 2026-08-18
> Primary decisions: [ADR-018](adr/ADR-018-git-native-local-editor.md), [ADR-019](adr/ADR-019-git-publication-boundary.md), [ADR-020](adr/ADR-020-knowledge-workspace-boundary.md)
> Evidence coordinates: [ADR-013](adr/ADR-013-evidence-anchor-coordinates.md)
> Open-source boundary: [`open-source-boundary.md`](open-source-boundary.md)

## 1. Product role

PcbKnowledge stores trusted PCB engineering knowledge together with exact source evidence. Agents prepare Source/Entity/Fact candidates; humans inspect evidence and typed closure; Git provides attribution, collaboration, and publication.

PcbKnowledge is intentionally separate from live board state. PcbCore owns components, nets, geometry, rules, connectivity, deterministic validation, and board mutation. PcbKnowledge owns external engineering knowledge such as datasheet limits, pin functions, application/layout guidance, fabrication constraints, internal rules, historical reviews, waivers, lifecycle state, and replacement relationships.

An Agent harness may combine both systems for a task, but PcbKnowledge is not a PcbCore runtime dependency and never mutates a PCB board.

## 2. Public software versus private knowledge workspace

The open-source software repository and a production knowledge repository are physically distinct Git repositories.

```text
PcbKnowledge/                    public software checkout
├── src/
├── configs/
├── schemas/                     source schema contract
├── docs/
├── tests/
├── static vendor assets
├── pcbknowledge.workspace.json  empty development contract
└── knowledge/evidence placeholders only

PcbKnowledgeData/                controlled knowledge workspace
├── .git/
├── pcbknowledge.workspace.json
├── schemas/                     pinned workspace contract
├── knowledge/
│   ├── sources/
│   ├── entities/
│   └── facts/
└── evidence/sha256/
```

A production workspace is self-contained. Its manifest, exact schema bytes, Source/Entity/Fact records, PDF evidence, review history, supersedes graph, and Git history define authority/publication. The public software checkout does not act as a hidden schema or data side channel for a published workspace.

Initialization copies the current schema snapshot, writes canonical `pcbknowledge.workspace.json`, and creates empty authority/evidence directories. It does not stage, commit, push, or silently upgrade an existing workspace.

Runtime selection is explicit:

```text
Agent CLI                  --repo <workspace>
Run/Open/Test/Package      --workspace <workspace>
```

An invalid explicit workspace never falls back to the public checkout.

## 3. Authority model

Canonical workspace authority is:

```text
knowledge/sources/      SourceRecordV1
knowledge/entities/     EntityRecordV1
knowledge/facts/        FactRecordV1
evidence/sha256/        immutable PDF originals
```

The initial entity set is Manufacturer, Component, and Package. The initial Fact set is ComponentPin and ParameterLimit.

Raw manufacturer/MPN/package text is preserved. Normalized fields exist for exact lookup only; package, silicon revision, orderable part, or family is not guessed from an MPN suffix.

Unknown is a valid result. Missing facts are never filled from a similar device, a similar package, free text, or model prior.

## 4. Evidence identity

A Source represents one exact engineering-document revision. Its PDF is addressed by actual SHA-256 bytes:

```text
evidence/sha256/<first-two>/<sha256>.pdf
```

The repository validates PDF path, SHA-256, size, media type, orphan state, symlinks, shared references, and committed/published evidence before authority is considered valid.

A Fact carries one or more `EvidenceAnchorV1` values:

```text
source_id
page                 # 1-based
coordinate_space     # PDF_NORMALIZED_V1
bbox                 # x0,y0,x1,y1 in [0,1]
quote
quote_sha256
```

ADR-013 defines `PDF_NORMALIZED_V1` against the displayed page after intrinsic crop and rotation, with top-left origin, X right, Y down, and coordinates normalized by displayed viewport width/height. Browser zoom and device-pixel ratio do not change anchor identity.

An anchor remains bound to one Source revision and never follows a replacement revision automatically.

## 5. Review state and publication

Source and Fact records use:

```text
DRAFT -> READY_FOR_REVIEW -> APPROVED
  ^              |
  +-- REJECTED <-+
```

Review history is append-only. Rejection comments survive edit/resubmission. A committed `APPROVED` record is immutable in place; corrections use a new record and explicit `supersedes`.

Working-tree approval and publication are distinct:

```text
working tree DRAFT / READY_FOR_REVIEW
    = preparation

working tree APPROVED
    = human approved, not yet published

committed APPROVED in publication ref
    = Published Knowledge
```

Formal readers resolve one immutable Git ref and validate the entire Source/Entity/Fact/evidence closure from that snapshot.

## 6. Runtime architecture

The runtime remains one loopback-only Python process:

```text
HTTP transport/security
        |
        v
WorkbenchApplication / review applications
        |
        v
KnowledgeRepository / domain model
        |
        v
selected Git workspace

HTML renderers <- typed view models
PDF.js canvas <- allowlisted local Source evidence endpoint
```

The server owns HTTP parsing, loopback Host/Origin checks, CSRF, response security headers, optimistic revision transport, and route dispatch. Application code builds typed projections and owns human review orchestration. Repository/domain code owns validation and canonical writes. HTML/JavaScript do not become authority.

The runtime has no login system, Docker dependency, database authority, queue, object store, reverse proxy, hosted service, or background worker.

## 7. Typed workbench

Active routes:

```text
/review
/sources
/sources/<id>
/entities
/entities/<id>
/facts
/facts/<id>
/diff
```

The old Source-only `/records/**` family is retired with no compatibility alias.

The workbench derives Source/Entity/Fact/supersedes/conflict navigation from canonical IDs. It does not store a second graph or mutable UI copy of authority.

Every page identifies the exact selected workspace. The `/diff` view is read-only; GUI code never runs Git add/commit/push.

## 8. Visual evidence review

Fact detail contains a read-only evidence projection:

```text
Fact typed payload
+ component/package identity
+ conditions/applicability
+ exact Source revision
+ page/bbox/quote/hash
        |
        v
local PDF.js canvas + normalized SVG overlay
```

PcbKnowledge vendors the reviewed `pdfjs-dist` 6.2.108 legacy display module and worker plus upstream license. Package integrity, exact file set, byte sizes, and SHA-256 values are pinned and checked in CI and again before the workspace server starts.

Runtime assets and PDF fetches are same-origin under CSP. The vendor directory is not generally browsable; only required runtime modules are allowlisted.

Source license policy is enforced twice: evidence-review projections omit blocked PDF URLs, and the loopback HTTP evidence endpoint independently returns 403 for a blocked Source. A browser cannot bypass the domain gate by constructing a URL manually.

## 9. Human decision closure

P0.3c completes the human decision boundary for Source and Fact authority.

A decision projection contains:

```text
record status
next-commit change scope
approval-only blockers
decision blockers
exact selected closure paths
selected Git status
selected diff
can_approve / can_reject
```

The selected closure is read-only derived Git state. For a Fact it includes the Fact, subject entities, Component manufacturer, referenced Sources, referenced PDF evidence, and a superseded Fact when applicable. Unrelated workspace data is excluded from that projection.

Decision scope semantics:

```text
CLEAN      allowed
DATA_ONLY  allowed
CODE_ONLY  blocked
MIXED      blocked
```

`CLEAN` is allowed because the review write itself will become `DATA_ONLY`. `CODE_ONLY` and `MIXED` block both approval and rejection so review history cannot be mixed into a software/schema/policy commit candidate.

Fact approval additionally requires:

- complete EvidenceAnchors;
- no unresolved semantic conflict;
- every referenced Source is `APPROVED`;
- referenced Source PDF evidence exists;
- Source license permits evidence processing.

Rejection may proceed while those business blockers exist because rejection is how a human returns an invalid candidate, but status/scope gates still apply.

The UI displays these gates, but display state is not trusted. POST handlers recompute the same decision immediately before calling the existing repository `approve_*` / `reject_*` mutation methods. No second write path was introduced.

Approved Facts show immutable UX and expose no approve/reject/edit form.

## 10. Git change-scope contract

The repository classifies the next commit candidate as:

```text
CLEAN
DATA_ONLY
CODE_ONLY
MIXED
```

Staged paths take precedence when a staged candidate exists; otherwise unstaged/untracked workspace paths are considered. Knowledge/evidence cannot share a commit with software/schema/policy changes.

Inside a knowledge workspace, Source/Entity/Fact/evidence changes are data. Manifest/schema migrations are contract changes and must be separate from data that depends on them.

## 11. Security and trust boundary

The current product assumes one trusted local user with OS filesystem/Git permissions. The editor binds only to loopback.

Mutation routes require:

- loopback Host validation;
- loopback Origin validation when Origin is present;
- CSRF token;
- optimistic revision token;
- domain/repository validation;
- P0.3c review-decision revalidation for human Source/Fact decisions.

A shared network editor, accounts, SSO, ACLs, compliance audit, or remote service requires a new threat model and ADR. Exposing the current loopback server to a network is not an incremental deployment option.

## 12. Derived state and packaging

Permanent authority is limited to workspace manifest/schemas, Source/Entity/Fact JSON, PDF originals, EvidenceAnchors, review/supersedes/conflict relationships, and Git history.

Derived/rebuildable state may include `.pcbknowledge/`, SQLite/FTS indexes, page text, thumbnails, rendered canvases, embeddings, summaries, caches, and package ZIPs.

`package --workspace <path>` validates the selected workspace and exports its manifest, pinned schemas, authority, and referenced evidence. Generated ZIP/SHA-256 outputs live under the software checkout's ignored `build/` tree and never become workspace authority.

## 13. FreeCM lifecycle

- **Config** validates the software checkout and writes a configuration receipt.
- **Build** compiles and runs repository tests, validates the empty source-checkout workspace, and writes a build receipt.
- **Run/Open** require the software build, validate the selected workspace and pinned viewer assets, and start the loopback editor.
- **Test** runs software tests and may additionally validate an external workspace.
- **Package** exports one validated selected workspace.

## 14. Next stage: real-data validation

P0.4a intentionally prioritizes a small real private workspace over more infrastructure. The pilot must validate the completed ingestion/review loop on 3–5 ICs and real PDFs before schema expansion or retrieval work.

The first pilot is also the first human pixel-level browser acceptance for PDF/bbox placement. It should include difficult material when available: intrinsic crop/rotation, complex fonts, table cells, multi-line conditions, footnotes, multiple anchors, package applicability, revision drift, and deliberately wrong/ambiguous cases.

P1 exact/FTS retrieval begins only after a real published dataset exists. Broader Fact families begin only after P0.4 demonstrates the current model's actual gaps.

## 15. Explicitly deferred capabilities

The following are not P0 requirements: hosted multi-user service, login infrastructure, database/object-store authority, MCP as a domain protocol, vector retrieval without evaluation evidence, automatic Git publication, automatic PCB mutation, or a second browser-framework build system. Changing these boundaries requires an explicit ADR rather than silently reviving a superseded design.
