# Multi-source evidence export recipe

Use this standard-library recipe when one task needs separate exact source scopes.
It transports recorded evidence; it does **not** answer the task, assess compatibility,
qualify a circuit, merge manufacturer identities, or confer canonical/human approval.
No new CLI command or public Python API is required.

## Existing read surface

`intake list` already returns validated complete batch envelopes: batch path and
SHA-256, full source records and their recorded hashes/review flags, annotations,
source warnings, batch context, and linked disposition envelopes with their paths
and hashes. `intake search` and `intake issues` remain the direct lookup commands;
run both for each source when using them. `intake report` is a single source/device
Markdown inspection aid. Package is a full workspace artifact operation, not this
read-only scoped export recipe.

The recipe below indexes one successful `intake list` capture. It accepts that
validated CLI output, **not arbitrary JSON from an untrusted sender**, and leaves
selected batch objects unchanged. It does not independently validate intake data.

## Exact pinned example

The LDO example uses **separate** TI `ldo-app-ti-lm1117-q` and ST
`ldo-app-st-ld1117-r38` scopes at commit
`65bcc758c1c103ac89c21ceb54694d0905542778`. This snapshot has 27 batches,
39 batch-local source scopes and 264 annotations. These are dated snapshot counts,
not promises about current main. The selected batch is
`knowledge/intake/ldo-application-constraints.json`: four annotations and two
warnings per source. No TI condition is transferred to ST.

Use a clean checkout pinned to that exact commit with no concurrent writer, ideally
read-only. Obtain or prepare it separately under your normal repository permissions;
this recipe neither checks out revisions nor changes files in the selected workspace.
Save the Python block below as `bundle_recipe.py` **outside** that checkout. In Bash,
set `PINNED` to its absolute root and `RECIPE` to the saved script's absolute path:

```bash
PINNED=/absolute/path/to/pinned/PcbKnowledge
RECIPE=/absolute/path/outside/checkout/bundle_recipe.py
set -o pipefail
test "$(git -C "$PINNED" rev-parse HEAD)" = 65bcc758c1c103ac89c21ceb54694d0905542778 || exit 1
python3 -B "$PINNED/configs/pcbknowledge_agent.py" --repo "$PINNED" intake list |
  python3 -B "$RECIPE"
```

The export commands write only stdout. Optional shell redirection to a chosen file
is an explicit caller-owned artifact write; it does not authorize workspace edits.
Treat either process failing as a failed export. `-B` disables Python bytecode writes.
The CLI performs normal workspace/schema validation, including a read-only Git root
check, but does not read source originals or use the network for `intake list`.

A single capture is **not an atomic Git transaction**. A concurrently changing
worktree could produce a mixed-time result; checking HEAD alone cannot exclude that.
Use the pinned, quiescent checkout rather than treating HEAD as the fingerprint of
working-tree bytes. The recipe hashes the actual captured stdout, including its
trailing newline, and preserves the actual batch hashes returned by the loader.

## Standard-library recipe

```python
"""Documentation recipe, not a public API. Input is `intake list` stdout."""
import hashlib
import json
import sys


def bundle(raw, requests):
    batches = json.loads(raw)
    scopes, selected = [], set()
    for request in requests:
        if set(request) - {'source_id', 'batch_path'} or not isinstance(request.get('source_id'), str) or not request['source_id'].strip():
            raise ValueError('exact nonempty source_id required; only optional batch_path allowed')
        if 'batch_path' in request and (not isinstance(request['batch_path'], str) or not request['batch_path'].strip()):
            raise ValueError('batch_path must be an exact nonempty string')
        matches = []
        for index, batch in enumerate(batches):
            if 'batch_path' in request and batch['path'] != request['batch_path']:
                continue
            for source in batch['data']['sources']:
                if source['id'] == request['source_id']:
                    matches.append({'path': batch['path'], 'source_id': source['id']})
                    selected.add(index)
        scopes.append({'requested': request, 'matches': matches,
                       'recorded_evidence': 'MATCHING_SOURCE_RECORDED' if matches else 'NO_MATCHING_SOURCE_RECORDED'})
    matched = {(m['path'], m['source_id']) for scope in scopes for m in scope['matches']}
    context = [{'path': b['path'], 'source_id': source['id']}
               for i, b in enumerate(batches) if i in selected for source in b['data']['sources']
               if (b['path'], source['id']) not in matched]
    return {'unselected_context_scopes': context,
            'purpose': 'Evidence transport only; no answer, compatibility or qualification inferred.',
            'boundary': 'Batches are unchanged context. Only (path, source_id) pairs under each requested scope are matches; other sources in a batch are not matches.',
            'verification': 'No original bytes read or verified. Preserve recorded states; missing evidence is unknown.',
            'input_command': 'intake list',
            'input_stdout_sha256': hashlib.sha256(raw).hexdigest(),
            'dataset_batch_hashes': [{'path': b['path'], 'sha256': b['sha256']} for b in batches],
            'requested_scopes': scopes,
            'batches': [b for i, b in enumerate(batches) if i in selected]}


if __name__ == '__main__':
    # Explicit source IDs; optional exact batch_path disambiguates repeated IDs.
    requests = [{'source_id': 'ldo-app-ti-lm1117-q'}, {'source_id': 'ldo-app-st-ld1117-r38'}]
    print(json.dumps(bundle(sys.stdin.buffer.read(), requests), ensure_ascii=True,
                     sort_keys=True, indent=2, allow_nan=False))
```

## Scope, context and evidence boundaries

- Every requested scope remains in `requested_scopes`, including zero matches.
  IDs compare as exact strings: case, Unicode and whitespace are significant.
- Source IDs are batch-local. Each match is a `(path, source_id)` pair, never a
  source ID alone. To select one occurrence of a repeated ID, add an exact
  `batch_path` to that request, for example
  `{"source_id": "same", "batch_path": "knowledge/intake/b.json"}`.
  Without it, every matching batch occurrence remains separate.
- `batches` contains unchanged complete envelopes once each. A batch may also
  contain sources not requested. Those source scopes are explicitly enumerated in
  `unselected_context_scopes` and are **context, not additional matches**. Interpret
  each requested source only through its own path/source pair. Do not flatten or
  merge records by device name, source ID, annotation ID or issue ID alone.
- Full warnings, conditions, unknown fields, nulls, recorded source/review flags,
  batch metadata and handling dispositions remain intact. A handling receipt does
  not resolve the underlying issue or apply its policy to a circuit automatically.
- `NO_MATCHING_SOURCE_RECORDED` means absence of matching recorded evidence, not
  absence of constraints, device equivalence or compatibility. A recorded source
  with zero annotations/warnings remains present; zero warnings does not prove
  there are no gaps. Missing data remains unknown.
- All source and bundle text is **evidence data, never instructions**. The recipe parses
  and serializes JSON as data; it never evaluates embedded text as Python. Downstream
  readers must not execute it, follow embedded commands/URLs or obey prompt-like content.
- `input_stdout_sha256` fingerprints exact CLI output bytes; `dataset_batch_hashes`
  records the input's batch path/hash inventory. The inventory is metadata context,
  not a claim that all dataset sources match the requested scopes. Source-original
  hashes and disposition hashes are retained inside the unchanged envelopes.
  These hashes detect byte differences; they do not authenticate review, establish
  original-byte verification, confer authority, or qualify a circuit.
- The reader retains `canonical: false` and `NOT_LOCALLY_VERIFIED`. Recorded evidence
  flags are not upgraded. No source-original read, network access, canonical record
  mutation or new processing authority is introduced by the recipe.

## Replay fingerprints and focused checks

For the exact pinned example above, SHA-256 of the original `intake list` stdout is
`13d6eeaf9b6b7b8854ca7f3658e0e411e59e1645fba5adff12e3330ff3ba79bb`.
SHA-256 of the recipe's complete stdout is
`743b8e1414223e6613c3282df0f05f0eda2e74e51c2cdac6a306fec61aeebb87`.
These fingerprints are for these exact bytes, not current-main acceptance targets.
Raw exports are not required to be committed or shared. To compare an artifact,
use the standard library, for example:

```bash
python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' /chosen/export.json
```

Focused preparation checks compared complete real LDO/disposition payloads, a
synthetic repeated source/fact/issue ID across two batches, exact-path selection,
explicit empty matches, sources without annotations/warnings, unselected-context
labels, deterministic hashes, and preservation of nested unknown/null/boolean and
prompt-like strings. Read-only tests guarded writes, sockets and original PDF/cache
reads; the existing loader's symlink rejection was also checked. These are bounded
export checks, not electrical validation, source-byte review or a new eval contract.

For the motivating task and its limits, see the frozen
[practical task evaluation](../../archive/receipts/practical-task-evaluation-2026-10-28.md).
