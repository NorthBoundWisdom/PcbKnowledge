# ADR-020: Separate the software checkout from knowledge workspaces

- Status: Accepted
- Date: 2026-08-18
- Extends: ADR-018, ADR-019

## Context

ADR-018 established a local Git-native editor where Git files are the authority, and ADR-019 made an immutable Git commit the publication boundary. The initial implementation used the PcbKnowledge source checkout itself as that Git repository.

Open-sourcing the software changes the distribution boundary. The public upstream must remain free of production Source/Entity/Fact data, internal review history, and third-party PDF originals, while real knowledge still needs a self-contained Git history whose published snapshots do not depend on mutable software-checkout files.

The Agent CLI already accepted an explicit repository path, but the GUI, FreeCM workflow, packaging, and schema contract still assumed the software checkout. Building the P0.3 review workbench on that assumption would bind real data to the wrong repository and conflict with the public-source guard.

## Decision

PcbKnowledge separates **software installation/source** from **knowledge workspace authority**.

A production knowledge workspace is a dedicated Git repository containing:

```text
pcbknowledge.workspace.json
schemas/
  source-record.schema.json
  entity-record.schema.json
  fact-record.schema.json
knowledge/
  sources/
  entities/
  facts/
evidence/sha256/
```

The public PcbKnowledge repository keeps only empty authority/evidence placeholders and may act as an empty development workspace for software validation. Production knowledge belongs in a separately controlled repository.

### Workspace manifest

`pcbknowledge.workspace.json` is canonical JSON and pins:

- workspace format: `pcbknowledge-workspace-v1`;
- schema contract: `typed-v1`;
- a SHA-256 schema digest;
- the PcbKnowledge creator marker.

The schema digest covers the exact bytes of all three schema files through their deterministic Git blob identities plus their repository paths. Filesystem metadata does not participate in the digest.

A manifest/schema mismatch fails closed. Initialization never silently upgrades an existing workspace. Future schema upgrades require an explicit workflow and a separate contract commit.

### Self-contained publication

The workspace carries the schema snapshot required to interpret its authority. Formal published reads continue to validate Source/Entity/Fact/evidence closure from one immutable Git ref. Supported published Agent entry points additionally validate the workspace manifest and schema digest from that same ref before returning published data.

The software checkout is not consulted as a mutable schema authority for an already-created workspace.

### Workspace initialization

`configs/pcbknowledge_workspace.py init <path>` initializes a clean Git repository by copying the current schema snapshot, writing the canonical workspace manifest, and creating empty authority/evidence directory placeholders.

Initialization:

- is idempotent only when the existing workspace already has the exact requested contract;
- rejects ambiguous or pre-existing authority data;
- can create a Git repository only with explicit `--init-git` and only for a missing or empty target;
- never stages, commits, or pushes files;
- creates no production data.

### Runtime selection

- Agent CLI: `--repo <workspace>`;
- Run/Open/Test/Package workflow: `--workspace <workspace>`;
- GUI repository reads/writes and Git diff operate only on the selected workspace;
- software code and static UI assets continue to come from the PcbKnowledge installation;
- no explicitly selected workspace silently falls back to the software checkout.

Package archives contain the selected workspace manifest, schema snapshot, authority, and referenced evidence. The ZIP itself remains derived build output under the software checkout rather than becoming knowledge authority.

### Commit separation after physical repository split

ADR-019 remains applicable. Production knowledge is now physically isolated from the software repository, but a workspace schema/manifest upgrade is still a contract/policy change. It must not share a commit with knowledge/evidence data that depends on the new contract.

## Consequences

### Positive

- The public repository can remain permanently free of production knowledge and redistributable third-party evidence.
- A private workspace can be backed up, reviewed, cloned, and published independently of the software checkout.
- Published knowledge remains hermetic because its schema contract travels with the data repository.
- The same PcbKnowledge executable can operate multiple explicitly selected workspaces without introducing a shared service or database.
- P0.3 can build its review UX around the correct long-term storage boundary.

### Costs

- Workspace creation has an explicit initialization step.
- Schema evolution requires a deliberate workspace contract upgrade instead of silently following the latest software checkout.
- Users must know which workspace is selected; the GUI and terminal therefore display the concrete workspace root.

## Rejected alternatives

### Keep production data in the public software repository

Rejected because it conflicts with copyright, confidentiality, and public-source distribution requirements.

### Load schemas dynamically from the software checkout

Rejected because old published knowledge could change meaning when the installed software changes, breaking snapshot hermeticity.

### Store only a software-version string in the workspace

Rejected because a version label does not prove which schema bytes are required to validate the published snapshot.

### Automatically stage or commit workspace initialization

Rejected because Git publication remains a deliberate human boundary and the application must not manipulate the index or publish on the user's behalf.
