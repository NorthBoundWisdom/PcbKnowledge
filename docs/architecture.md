# PcbKnowledge Git-native architecture

> Status: P0.3a Typed Workbench Foundation complete; P0.3b Evidence Review next
> Updated: 2026-08-18
> Primary decisions: [ADR-018](adr/ADR-018-git-native-local-editor.md), [ADR-019](adr/ADR-019-git-publication-boundary.md), [ADR-020](adr/ADR-020-knowledge-workspace-boundary.md)
> Open-source boundary: [`open-source-boundary.md`](open-source-boundary.md)

## 1. Product role

PcbKnowledge is a repository for PCB engineering knowledge and source evidence. Agents prepare sources and structured candidates; engineers or product managers inspect source material, reject or approve candidates, and use Git for attribution, collaboration, and final publication.

PCB software already knows the live board: components, nets, geometry, rules, connectivity, and deterministic DRC state. Many engineering decisions depend on information outside the board model, including:

- datasheet pin functions, absolute maximums, and recommended operating conditions;
- power sequencing, decoupling, clocks, reset behavior, and boot configuration;
- manufacturer layout/application guides and reference designs;
- fabrication capabilities, internal engineering rules, historical reviews, and waivers;
- PCNs, EOL information, lifecycle state, and replacement relationships.

These materials change by revision. An engineering conclusion therefore needs to answer which document, which revision, which page, and which source passage supports it. PcbKnowledge stores immutable evidence together with typed engineering facts instead of relying only on model memory or generic PDF chunk/vector retrieval.

PcbKnowledge is not a shared online service and is not part of PcbCore. PcbKnowledge provides external engineering knowledge and evidence; PcbCore owns live board facts and deterministic validation. An Agent harness may combine both systems for a task, but board mutation remains inside PcbCore contracts.

## 2. Software checkout versus knowledge workspace

The open-source software repository and a production knowledge repository are physically distinct Git repositories.

```text
PcbKnowledge/                    public software checkout
├── src/
├── configs/
├── schemas/                     source schema contract
├── docs/
├── tests/
├── pcbknowledge.workspace.json  empty development-workspace contract
└── knowledge/evidence placeholders only

PcbKnowledgeData/                private knowledge workspace
├── .git/
├── pcbknowledge.workspace.json
├── schemas/                     pinned workspace contract
├── knowledge/
│   ├── sources/
│   ├── entities/
│   └── facts/
└── evidence/sha256/
```

The public source checkout must stay free of production authority/evidence. It carries an empty workspace contract so software validation and default local smoke tests remain self-contained, but real data is written to an explicitly selected private workspace.

A production workspace is initialized with:

```bash
python3 configs/pcbknowledge_workspace.py init <workspace>
```

Initialization copies the three current schemas, writes canonical `pcbknowledge.workspace.json`, creates empty authority/evidence directories, and validates the result. It does not stage, commit, or push.

### 2.1 Workspace manifest

The workspace manifest pins:

```text
format            pcbknowledge-workspace-v1
schema_contract   typed-v1
schema_digest     SHA-256 contract digest
created_with      PcbKnowledge
```

The schema digest covers the exact bytes of all three workspace schemas through their deterministic Git blob identities plus their repository paths. A mismatch between manifest and schema bytes fails closed. Existing workspaces are never silently upgraded by `init`; schema migration requires an explicit future upgrade workflow.

### 2.2 Runtime selection

Supported runtime selectors are explicit:

```text
Agent CLI                  --repo <workspace>
Run/Open/Test/Package      --workspace <workspace>
```

No explicitly selected invalid workspace falls back to the public source checkout. Terminal receipts and the GUI show the concrete selected root.

Source code, Python modules, CSS, and other application assets come from the PcbKnowledge software installation. Source/Entity/Fact authority, evidence, review state, and Git diffs come only from the selected workspace.

## 3. Current runtime structure

```text
PcbKnowledge software checkout
        |
        | run/open --workspace <path>
        v
loopback Python typed workbench (127.0.0.1:18080)
        |
        | HTTP handler
        v
WorkbenchApplication / typed view models
        |
        v
KnowledgeRepository / domain model
        |
        v
selected knowledge Git workspace
  ├── pcbknowledge.workspace.json
  ├── schemas/
  ├── knowledge/
  └── evidence/
        |
        v
Git diff / human review / commit
```

HTML rendering is a pure projection of typed view models. HTTP handlers parse transport input, enforce loopback/CSRF/revision boundaries, invoke application operations, and map results to responses. The renderer does not rediscover Source/Entity/Fact relationships and no UI-side authority graph is stored.

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

Formal readers never treat the mutable working tree as published knowledge. The typed published reader resolves one immutable Git ref and validates from that snapshot:

- canonical Source/Entity/Fact JSON;
- filename and record identity;
- workspace-local schema documents;
- Source/Entity/Fact reference closure;
- `supersedes` closure;
- referenced PDF bytes;
- PDF SHA-256, size, and content-addressed path.

Supported published Agent entry points first validate `pcbknowledge.workspace.json` and its schema digest from the same ref, then invoke the typed published reader. Working-tree schema or license changes cannot weaken a committed published read.

### 4.2 Data commits and contract commits stay separate

Git change scope remains:

```text
CLEAN
DATA_ONLY
CODE_ONLY
MIXED
```

Inside a knowledge workspace, `knowledge/**` and `evidence/**` are data. Workspace manifest or schema changes are contract/policy changes and must not share a commit with data that depends on the new contract. In the public software repository, production data is prohibited entirely by `check_public_repo.py`.

## 5. Typed authority model

Canonical knowledge uses:

```text
knowledge/
├── sources/      SourceRecordV1
├── entities/     EntityRecordV1
└── facts/        FactRecordV1

evidence/sha256/ immutable PDF originals
```

The retired `knowledge/records/` Source-only wire format is historical and has no active read or dual-write path. The P0.3a HTTP UI also removes the retired `/records` route family rather than maintaining an alias.

### 5.1 SourceRecordV1

A Source represents one exact engineering-document revision. Core fields include stable ID/schema version, source type, title/document number/revision, publisher/locator, explicit license policy, content-addressed evidence, append-only review history, and explicit `supersedes`.

Revision relationships are stored explicitly and are never inferred from file names or titles.

### 5.2 EntityRecordV1

The P0 entity set is intentionally small:

```text
ManufacturerV1
ComponentV1
PackageV1
```

Raw manufacturer, MPN, and package strings are preserved. Normalized keys exist only for exact lookup. Package, silicon revision, orderable part, or family is never inferred from an MPN suffix.

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

An anchor binds to one immutable Source revision and never migrates automatically to another revision. Draft Facts may temporarily use page-only/incomplete anchors, but approval requires complete anchors.

### 5.4 FactRecordV1

A Fact is a typed PCB engineering assertion rather than a free-text summary. The first implemented types are `ComponentPinFactV1` and `ParameterLimitFactV1`, each carrying entity references, typed payload, conditions/applicability, evidence anchors, review history, and `supersedes`.

Numeric facts require explicit units. An unstated value remains unknown; it is not copied from a similar device or filled from model memory.

## 6. Review, immutability, and conflict handling

Source and Fact records use an explicit state machine:

```text
DRAFT -> READY_FOR_REVIEW -> APPROVED
  ^              |
  +-- REJECTED <-+
```

- submit, reject, and approve append review history;
- rejection comments survive edit/resubmission;
- committed `APPROVED` authority cannot be rewritten or deleted in place;
- corrections use a new identity/version plus `supersedes`;
- unresolved semantic conflicts remain explicit and are never resolved by model confidence;
- working-tree approval remains distinct from publication.

P0.3a exposes READY_FOR_REVIEW Source and Fact records through one typed queue. The queue projects missing Fact anchors, semantic conflicts, and Source approval/evidence closure as explicit blockers. It does not mutate or auto-resolve those blockers.

## 7. Source licensing and Agent processing

`SourceRecordV1` uses:

```text
UNKNOWN
PUBLIC_REFERENCE
OPEN_LICENSE
INTERNAL
RESTRICTED
LICENSED_BLOCKED_FOR_AI
```

`PUBLIC_REFERENCE` means publicly accessible, not automatically redistributable. `UNKNOWN`, `RESTRICTED`, and `LICENSED_BLOCKED_FOR_AI` fail closed for Agent/model source processing. IPC and equivalent restricted standards default to `LICENSED_BLOCKED_FOR_AI`.

Normal Agent Source projections do not reveal the evidence path. `source authorize-read` returns a path only after policy and bytes both pass validation.

## 8. Evidence lifecycle

PDF originals are addressed by actual SHA-256 bytes:

```text
evidence/sha256/<first-two>/<sha256>.pdf
```

The repository creates missing digest objects, reuses identical content, rejects hash/size/path mismatch and symlinks, validates orphan evidence, protects committed/published evidence, and serializes writes with a repository lock.

## 9. Derived data and packaging

Permanent workspace assets are:

```text
pcbknowledge.workspace.json
schemas/
Source / Entity / Fact JSON
PDF originals
EvidenceAnchor
review / supersedes / conflict relationships
Git history
```

Rebuildable state includes `.pcbknowledge/`, SQLite indexes, FTS, page text, thumbnails/previews, embeddings, summaries, caches, and package ZIPs.

`package --workspace <path>` validates and reads only the selected workspace. Its archive includes the workspace manifest, pinned schemas, authority, and referenced evidence. The ZIP and SHA-256 sidecar are written under the software checkout's ignored `build/package/` directory.

## 10. Agent boundary

P0.2 exposes typed `source`, `entity`, and `fact` command groups plus four repository-local skills. P0.2.5 makes workspace selection part of every skill contract.

Agents may create/edit drafts, create typed candidates, attach verified anchors, validate, submit for human review, and report unknown/conflict/missing-evidence/diff state.

Agents may not approve/reject, stage/commit/push, read blocked content, fill facts from approximate identities/model priors, silently switch workspaces, or mutate PCB board state.

## 11. Typed review workbench

P0.3a replaces the Source Corpus UI foundation with typed routes:

```text
/review                primary Source/Fact review queue
/sources               Source list
/sources/<id>          exact Source revision and human Source workflow
/entities              Manufacturer / Component / Package list
/entities/<id>         exact identity and related records
/facts                  typed engineering Fact list
/facts/<id>             typed payload, applicability, anchors, conflicts
/diff                   read-only workspace Git diff
```

The old `/records` route family is intentionally retired rather than retained as a compatibility alias.

The application layer constructs typed view models from one validated workspace snapshot. It derives:

- Source -> referencing Facts, predecessor/successor revisions;
- Manufacturer -> Components;
- Component/Package -> related Facts;
- Fact -> Component/Package identities, Source revisions, EvidenceAnchors, semantic conflicts, predecessor/successor Facts;
- READY_FOR_REVIEW Source/Fact queue items and current closure blockers;
- working-tree Git change count and change scope.

Source create/edit/submit/approve/reject remains available through `/sources/**` and continues to use optimistic revision tokens, append-only review history, evidence validation, and no Git write. Entity and Fact views are read-only in P0.3a.

P0.3b adds local visual evidence review: pinned PDF viewer assets, exact page rendering, and normalized bounding-box overlays. P0.3c adds Fact approve/reject controls plus final missing/conflict/license/change-scope closure in the typed review view.

The runtime remains server-rendered Python plus repository-owned static assets. P0.3a introduces no Node build chain and no JavaScript requirement.

## 12. FreeCM lifecycle

- **Config** validates the software checkout and writes a configuration receipt.
- **Build** compiles, runs focused tests, validates the empty source-checkout workspace, and writes a build receipt.
- **Run/Open** require the software build, validate the selected workspace, and start the loopback editor.
- **Test** runs software tests and may additionally validate an external `--workspace`.
- **Package** requires the software build and exports the selected validated workspace.

FreeCM's default actions continue to target the source checkout for development convenience. Terminal users select production/private workspaces explicitly with `--workspace`.

## 13. Retrieval and product integration direction

P1 query order remains:

```text
exact entity
-> exact package / revision / fact type
-> published filters
-> FTS
-> fact + evidence + conflict + unknown
```

Broader Fact types are added only after the first real dataset validates the initial schema and review UX. P2 introduces immutable KnowledgeSnapshot consumption and read-only PCBAtlas/PcbCore-facing Agent adapters without making PcbKnowledge a live board dependency.

## 14. Explicitly deferred capabilities

The following are not P0 requirements: hosted multi-user service, login infrastructure, database/object-store authority, MCP as a domain protocol, vector retrieval without evaluation evidence, automatic Git publication, and automatic PCB board mutation. Changing these boundaries requires an explicit ADR rather than silently reviving a superseded design.
