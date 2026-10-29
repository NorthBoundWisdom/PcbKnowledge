# Offline intake handoff preflight

`configs/pcbknowledge_intake_handoff.py` observes an immutable additive handoff
against a pinned target commit. It does not integrate or approve it.

```sh
python3 configs/pcbknowledge_intake_handoff.py \
  --object-repo /absolute/path/to/local-repository \
  --delivery FULL_40_CHARACTER_DELIVERY_SHA \
  --base FULL_40_CHARACTER_PARENT_SHA \
  --target FULL_40_CHARACTER_TARGET_SHA \
  --json-sha256 INDEPENDENTLY_REVIEWED_JSON_SHA256 \
  --review-sha256 INDEPENDENTLY_REVIEWED_MARKDOWN_SHA256
```

All three commits and their trees/blobs must already exist in the same local
SHA-1 object store. Ordinary repositories with a `.git` directory and bare Git
directories are supported. Linked worktree gitfiles, alternate object stores,
symlinked/reparse object roots or contents, special files, and missing objects are
rejected. Use the owning ordinary/bare repository for a linked worktree; the
command does not discover or follow its gitfile. A dirty worktree is irrelevant:
no index, worktree file or ref is used as content authority. Inputs and the
installed Git executable must remain stable during inspection; concurrent
hostile object-store modification is outside the OS-access trust boundary.

Supply both lowercase SHA-256 pins from a separately reviewed receipt. This
command deliberately has no pin-generation or expected-output update mode.
Caller-supplied pins prove a byte match, not the authenticity of their author.
Commit inputs require complete lowercase 40-character IDs, not refs or Git
revision expressions.

## Checks and boundaries

- The delivery has exactly one parent, equal to the supplied base.
- Only two new `100644` blobs may differ: `knowledge/intake/<stem>.json`
  and `knowledge/intake/<stem>-review.md`, with a lowercase alphanumeric/hyphen
  stem. Changes to unrelated directories, deletions and modifications fail.
- Both paths must be absent from base and target, including directory collisions;
  the `knowledge` and `knowledge/intake` ancestors must be trees if present.
- Git object identities are recomputed from their typed content; merely finding
  a file under the supplied object name is insufficient. Object sizes are checked
  before loading contents. Each commit, tree and pair
  blob is limited to the existing one-million-byte intake ceiling; each snapshot
  is limited to 20,000 entries and 32 tree levels. Pair contents must be UTF-8.
- JSON parsing rejects duplicate keys and non-finite constants. The existing
  intake structural/provenance validator and source-warning reference validator
  remain the authority. `human_reviewed` must explicitly be false.
- IDs are unique within each batch's record kind, not globally across batches.
  Repeated source IDs, devices or source PDF digests in different batch paths
  are legitimate; the existing query identity includes batch context. No
  semantic deduplication or source-truth assessment is attempted.

Git runs with a minimal environment and a temporary isolated Git control
directory. Input repository configuration, system/global configuration, replace
refs, caller Git environment overrides, hooks, protocols and lazy fetching are
not used. Object alternates are rejected rather than traversed. The only writes
are disposable control files outside the input repository; no input objects,
refs, cache, worktree, schema, manifest or expected outputs are written.
A temporary root inside the selected input repository is rejected before control
files are created. Git calls have a 20-second timeout. Permissions/read errors
fail closed.

Success exits zero with `PREFLIGHT_COMPATIBLE_ONLY`, the three pinned commit IDs,
observed blob IDs, SHA-256 digests and byte sizes. Rejection exits two with
`PREFLIGHT_REJECTED`. Neither result authenticates a reviewer or verifies source
bytes, visual evidence, semantics, global replay, dispositions, CI, packaging,
canonical approval or publication. Target compatibility expires when the
integrator chooses another target: rerun against that full commit ID. The
integrator still owns aggregate evaluation and acceptance; this is not a second
acceptance framework.

## Verification

Synthetic real-object tests live in `tests/git_native/test_intake_handoff.py`:

```sh
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_intake_handoff -v
```

They cover immutable/dirty-worktree reads, independent pins, additive scope,
parentage, unsafe ancestors/modes, bounded objects, strict parsing, batch-local
IDs, warning references, environment/config isolation and explicit rejection.
