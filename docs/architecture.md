# PcbKnowledge Git-native architecture

> Status: P0.2 Agent-native ingestion complete; P0.2.5 workspace separation is next
> Updated: 2026-08-18
> Primary decisions: [ADR-018](adr/ADR-018-git-native-local-editor.md), [ADR-019](adr/ADR-019-git-publication-boundary.md)
> Open-source boundary: [`open-source-boundary.md`](open-source-boundary.md)

## 1. Product role

PcbKnowledge is a repository for PCB engineering knowledge and source evidence. Agents prepare sources and structured candidates; engineers or product managers inspect the source material, reject or approve candidates, and use Git for attribution, collaboration, and final publication.

PCB software already knows the live board: components, nets, geometry, rules, connectivity, and deterministic DRC state. Many engineering decisions depend on information outside the board model, including:

- datasheet pin functions, absolute maximums, and recommended operating conditions;
- power sequencing, decoupling, clocks, reset behavior, and boot configuration;
- manufacturer layout/application guides and reference designs;
- fabrication capabilities, internal engineering rules, historical reviews, and waivers;
- PCNs, EOL information, lifecycle state, and replacement relationships.

These materials change by revision. An engineering conclusion therefore needs to answer which document, which revision, which page, and which source passage supports it. PcbKnowledge stores immutable evidence together with typed engineering facts instead of relying only on model memory or generic PDF chunk/vector retrieval.

PcbKnowledge is not a shared online service and is not part of PcbCore. The system prioritizes:

- traceability from engineering facts to exact source revisions;
- explicit unknown, conflict, licensing, package, and revision states;
- one authority model shared by humans and Agents;
- reviewable Git diffs and immutable publication snapshots;
- failure isolation from PcbCore and PCBAtlas board-opening/editing paths.

PcbKnowledge provides external engineering knowledge and evidence. PcbCore owns live board facts and deterministic validation. An Agent harness may combine both systems when performing a task, but board mutation remains inside PcbCore contracts.

## 2. Software repository versus knowledge workspace

The open-source software repository and a production knowledge repository have different responsibilities.

```text
PcbKnowledge/                    public software checkout
├── src/
├── configs/
├── schemas/
├── docs/
├── tests/
└── knowledge/evidence placeholders only

PcbKnowledgeData/                private knowledge workspace
├── .git/
├── schemas/                     pinned workspace contract
├── knowledge/
│   ├── sources/
│   ├── entities/
│   └── facts/
└── evidence/sha256/
```

The public source checkout must stay data-empty. Production authority and evidence belong in a separately controlled Git workspace. The Agent CLI already supports an explicit repository through `--repo`; P0.2.5 extends this boundary to workspace initialization, the GUI, FreeCM actions, packaging, and schema-contract pinning.

A knowledge workspace remains self-contained. Formal publication must not depend on mutable files from the software checkout. The schemas, Source/Entity/Fact records, referenced evidence, and publication ref required to validate a snapshot must be available from the same workspace repository state.

## 3. Current runtime structure

Before P0.2.5, the local editor still defaults to its own checkout as the repository root:

```text
FreeCM Run
   |
   v
loopback Python editor (127.0.0.1:18080)
   |
   +--> selected/current Git repository
   |      ├── schemas/
   |      ├── knowledge/
   |      └── evidence/
   |
   v
Git diff / human review / commit
```

The runtime is one Python process with server-rendered HTML and repository-owned CSS. It has no Node build chain, Docker runtime, reverse proxy, database, queue, object store, identity provider, or background worker.

Local operating-system permissions and Git repository permissions define the current trusted-user boundary. A future shared online editor, enterprise SSO, fine-grained ACL, or compliance-grade audit system requires a new threat model and a new ADR; exposing the loopback editor to a network is not an incremental deployment option.

## 4. Git authority and publication boundary

### 4.1 Working tree, approval, and publication are distinct

```text
working tree DRAFT / READY_FOR_REVIEW
    = preparation in progress

working tree APPROVED
    = human-approved, not yet published

committed APPROVED in publication ref
    = Published Knowledge
```

Formal readers never treat the mutable working tree as published knowledge. The published reader resolves one immutable Git ref and validates, from that same snapshot:

- canonical JSON;
- filename and record identity;
- schema contract;
- Source/Entity/Fact reference closure;
- `supersedes` closure;
- referenced PDF bytes;
- PDF SHA-256, size, and content-addressed path.

The typed published reader and `list --published` follow this rule and do not borrow uncommitted working-tree JSON, schema, license state, or evidence.

### 4.2 Data commits and policy commits stay separate

Git change scope is classified as:

```text
CLEAN
DATA_ONLY
CODE_ONLY
MIXED
```

Inside a knowledge workspace, `knowledge/**` and `evidence/**` are data. Schema or workspace-contract upgrades are policy/contract changes and must be committed separately from data that relies on the new contract. When the Git index is non-empty, classification describes the actual staged commit candidate; otherwise it describes unstaged/untracked changes. Both sides of rename/copy operations participate in classification.

`MIXED` is invalid for a single publication commit. This prevents one change from weakening or changing validation policy while simultaneously publishing data that only passes under the new policy.

## 5. Typed authority model

Canonical knowledge uses:

```text
knowledge/
├── sources/      SourceRecordV1
├── entities/     EntityRecordV1
└── facts/        FactRecordV1

evidence/sha256/ immutable PDF originals
```

The retired `knowledge/records/` Source-only wire format is historical and has no active read or dual-write path.

### 5.1 SourceRecordV1

A Source represents one exact engineering-document revision, not all knowledge about a component. Core fields include:

- stable ID and schema version;
- `source_type`: `DATASHEET`, `APPLICATION_NOTE`, `REFERENCE_DESIGN`, `PCN`, `FAB_CAPABILITY`, or `INTERNAL_GUIDELINE`;
- title, document number, and revision;
- publisher and source locator;
- explicit license policy;
- content-addressed evidence;
- append-only review history;
- explicit `supersedes`.

Revision relationships are stored explicitly and are never inferred from file names or titles.

### 5.2 EntityRecordV1

The P0 entity set is intentionally small:

```text
ManufacturerV1
ComponentV1
PackageV1
```

Invariants:

- raw manufacturer, MPN, and package strings are preserved;
- normalized keys exist only for exact lookup;
- package, silicon revision, orderable part, or family is never inferred from an MPN suffix;
- identity creation is stable and idempotent;
- Component references Manufacturer explicitly, while Package is modeled independently.

### 5.3 EvidenceAnchorV1

ADR-013 defines evidence coordinates:

```text
source_id
page                 # 1-based
coordinate_space     # PDF_NORMALIZED_V1
bbox                 # x0,y0,x1,y1 in [0,1]
quote
quote_sha256
```

A complete bounding box satisfies:

```text
0 <= x0 < x1 <= 1
0 <= y0 < y1 <= 1
```

An anchor binds to one immutable Source revision and never migrates automatically to another revision. Draft Facts may temporarily use incomplete/page-only anchors, but approval requires complete evidence anchors.

### 5.4 FactRecordV1

A Fact is a typed PCB engineering assertion rather than a free-text summary:

```text
stable identity
fact_type
subject entity IDs
payload
conditions/applicability
evidence anchors
review history
supersedes
```

The first implemented Fact types are:

**ComponentPinFactV1**

- component ID;
- package ID;
- pin number/name;
- primary function;
- alternate functions;
- conditions/applicability;
- one or more evidence anchors.

**ParameterLimitFactV1**

- component ID;
- parameter;
- `ABSOLUTE_MAXIMUM`, `RECOMMENDED_OPERATING`, or `ELECTRICAL_CHARACTERISTIC`;
- minimum / typical / maximum;
- unit;
- conditions;
- one or more evidence anchors.

Numeric facts require explicit units. An unstated value remains unknown; it is not copied from a similar device or filled from model memory.

## 6. Review, immutability, and conflict handling

Source and Fact records use an explicit state machine:

```text
DRAFT -> READY_FOR_REVIEW -> APPROVED
  ^              |
  +-- REJECTED <-+
```

- submit, reject, and approve append review history;
- rejection comments are preserved through edit and resubmission;
- committed `APPROVED` authority cannot be rewritten or deleted in place;
- corrections use a new identity/version plus `supersedes`;
- unresolved semantic conflicts remain explicit and are never resolved by model confidence;
- working-tree approval remains distinct from publication.

A reviewer is responsible for checking source identity, revision, licensing, structured fact content, and original evidence. High-risk engineering claims require a reviewer with appropriate domain judgment. The validator detects duplicate/conflicting semantic facts and prevents multiple active contradictory approved facts from being treated as one authoritative answer.

## 7. Source licensing and Agent processing

`SourceRecordV1` uses the following explicit taxonomy:

```text
UNKNOWN
PUBLIC_REFERENCE
OPEN_LICENSE
INTERNAL
RESTRICTED
LICENSED_BLOCKED_FOR_AI
```

Semantics:

- `PUBLIC_REFERENCE`: publicly accessible, but not necessarily redistributable;
- `OPEN_LICENSE`: explicitly open-licensed subject to that license;
- `INTERNAL`: internal processing is allowed in the controlled workspace;
- `RESTRICTED`: distribution/processing restrictions fail closed;
- `LICENSED_BLOCKED_FOR_AI`: Agent/model reading, parsing, indexing, embedding, or derived-content exposure is blocked;
- `UNKNOWN`: rights are uncertain, so processing fails closed.

IPC and equivalent restricted standards default to `LICENSED_BLOCKED_FOR_AI`.

Normal Agent Source projections do not reveal the evidence path. `source authorize-read` returns a path only after policy and bytes both pass validation.

## 8. Evidence lifecycle

PDF originals are permanently addressed by their actual SHA-256 bytes:

```text
evidence/sha256/<first-two>/<sha256>.pdf
```

Write rules:

- create if absent;
- reuse an identical digest;
- fail if hash, size, or path is inconsistent;
- reject symlinks and invalid layouts;
- treat unexplained orphan evidence as an integrity error;
- after replacing draft evidence, prune only an uncommitted original that is unreferenced both in the working authority and published ref;
- serialize multi-process writes with the repository lock.

## 9. Derived data and retrieval

Permanent assets are:

```text
Source / Entity / Fact JSON
PDF originals
EvidenceAnchor
review / supersedes / conflict relationships
Git history
```

Rebuildable derived state includes:

```text
.pcbknowledge/
SQLite indexes
FTS
PDF page text
thumbnail / preview
embedding / vector index
summary / cache
build/package
```

P0 does not require vector RAG. P1 introduces a local exact index plus SQLite FTS5. Vector retrieval enters P3 only if golden evaluation shows stable improvement for guideline/case retrieval over exact + FTS.

## 10. Agent boundary

P0.2 exposes the typed repository through explicit `source`, `entity`, and `fact` command groups plus four repository-local skills for Source ingestion, exact identity resolution, Fact extraction, and human handoff.

Entity resolution returns only `EXACT`, `UNKNOWN`, or `CONFLICT`. Fact projections expose optional unknowns, missing anchors, and semantic conflicts. `review-status` checks the selected Source/Entity/Fact closure and returns `WAIT_FOR_HUMAN_REVIEW` only when the candidate is complete, license-allowed, conflict-free, submitted, and `DATA_ONLY`.

Agents may:

- create and edit drafts;
- create typed Source/Entity/Fact candidates;
- attach verified EvidenceAnchors;
- validate;
- submit for human review;
- report unknowns, conflicts, missing evidence, and diffs.

Agents may not:

- approve or reject;
- stage, commit, or push;
- read blocked source content;
- fill facts from approximate MPNs, similar devices, or model priors;
- mutate PCB board state.

## 11. GUI evolution

The current GUI is the Source Corpus editor: it creates document records, attaches PDFs, submits/reviews Sources, and shows Git changes. It is not yet the final Fact Review Workbench.

P0.2.5 first makes workspace selection explicit. P0.3 then evolves the UI toward:

```text
/review                primary review queue
/sources
/entities
/facts

PDF page + normalized bbox overlay
+ typed fact inspector
+ review history
+ source/entity/fact/supersedes navigation
+ missing/conflict/license gates
+ Git diff and change-scope state
```

The runtime remains server-rendered Python plus a small amount of native JavaScript. No Node build chain is introduced for the P0 workbench.

## 12. FreeCM lifecycle

The current FreeCM protocol remains intentionally lightweight:

- **Config** checks Python/Git/runtime boundaries and writes a configuration receipt.
- **Build** compiles, runs focused tests, validates authority, and writes a build receipt.
- **Run/Open** verifies the build and starts the loopback editor.
- **Test** runs the local standard-library test suite and repository integrity gates.
- **Package** exports a deterministic validated knowledge snapshot.

P0.2.5 extends Run/Open/Package with an explicit `--workspace` and keeps the public software checkout data-empty.

## 13. Retrieval and product integration direction

The intended P1 query order is:

```text
exact entity
-> exact package / revision / fact type
-> published filters
-> FTS
-> fact + evidence + conflict + unknown
```

Broader Fact types such as package dimensions, power sequencing, decoupling, clock/reset rules, and layout guidelines are added only after the first real dataset validates the initial schema and review UX.

P2 introduces immutable KnowledgeSnapshot consumption and read-only adapters for PCBAtlas/PcbCore-facing Agent workflows. PcbKnowledge still does not become a live PcbCore dependency and never gains authority to mutate a board directly.

## 14. Explicitly deferred capabilities

The following are not P0 requirements:

- hosted multi-user service;
- account/login infrastructure;
- database authority;
- object-storage authority;
- MCP as a domain protocol;
- vector retrieval without evaluation evidence;
- automatic Git commit/push from the GUI or Agent;
- automatic board mutation.

Any future implementation that changes these boundaries requires an explicit architecture decision rather than silently reviving a superseded design.
