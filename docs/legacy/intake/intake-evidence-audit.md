# Explicit local intake evidence-byte audit

This audit currently requires POSIX descriptor-relative no-follow filesystem
operations (supported Linux/macOS environments). Windows and other platforms
without those primitives fail explicitly with exit status 2, before audit metadata
or cache access. There is no weaker fallback. Existing intake metadata commands
remain cross-platform; Windows support for secure byte auditing is not claimed.

The intake list, coverage and report readers expose recorded metadata, not local
original-byte verification. Use this separate audit when the original files are
already available locally and you want to compare their bytes to recorded pins:

```bash
python3 -B configs/pcbknowledge_agent.py --repo <workspace> intake evidence-audit \
  --cache-root <local-cache-directory> \
  --cache-file synthetic.bin --cache-file nested/synthetic-copy.bin \
  --source-id source-a
```

These are invented names, not source originals. `--cache-root` and at least one
repeatable `--cache-file` are required. Paths are explicit portable relative
paths beneath that root; there is **no scan, glob expansion, recursive discovery,
network request or automatic fetch**. A recorded path never causes a file to be
opened. Every listed candidate is checked, even if no source passes the optional
filters. The file suffix is not interpreted and PDF headers/content are not
parsed. This command does not import evidence into a canonical workspace.

Optional `--source-id`, `--manufacturer`, `--device`, `--package` and `--revision` filters use
the same exact structured string intersection as `intake search`. Source IDs
remain batch-local. With no filters, all recorded intake source scopes are
reported. Case, whitespace and Unicode are significant; missing/non-string
identity values cannot match a filter. The entire intake and its dispositions
are validated before any candidate bytes are read, including unrelated batches.
All non-null source hash/size pins must be well-formed, including unselected
sources: lowercase SHA-256 and positive non-boolean integer byte count.

## Reading the ephemeral JSON result

The output contains the actual intake batch SHA-256 and path, batch-local source
ID, recorded hash/byte count, and a separate `local_byte_check` for each source.
`associated_candidates` refers to the numbered candidate observations containing
actual SHA-256 and byte count (or null for a missing candidate). Nothing updates
recorded evidence grades, annotation statuses, owner acceptance or canonical
records. Other intake readers continue to report `NOT_LOCALLY_VERIFIED` because
they do not perform this audit or consume a persistent audit receipt.

| Local byte check | Meaning within this invocation |
| --- | --- |
| `FOUND_MATCH` | A listed candidate's actual SHA-256 **and** byte count equal the complete recorded pin. |
| `MISSING` | No matching or associated present candidate was found in the explicit list. Not a claim about other files. |
| `HASH_MISMATCH` | An associated candidate conflicts with the recorded hash or byte count; this also covers matching hash with conflicting recorded size. |
| `UNPINNED` | Recorded hash or size is absent/null. Unknown identity is not inferred from available files. |
| `AMBIGUOUS` | Associated present candidates contain different byte identities. Conflicting locator claims are retained rather than selecting one. |

Association uses actual matching SHA-256, an exact safe recorded `pdf_local_path`
or `evidence_cache_path`, or a basename exactly equal to `<recorded-sha256>.pdf`.
A friendly filename, source ID or URL does not establish association. Unsafe,
absolute or non-string recorded paths are ignored as locators, never followed.
Therefore a changed file with an arbitrary name and no recorded locator results
in `MISSING`, not a guessed mismatch. Source URLs and historical review receipts
are not alternative hash authorities.

Multiple listed paths with identical matching bytes yield `FOUND_MATCH` and
`matching_copy_count`, not content ambiguity. The count describes matching listed
candidate paths, not distinct physical copies; hard links/aliases may refer to
one file. Repeating the exact candidate path is an input error. A matching copy
plus a conflicting claimed locator is `AMBIGUOUS`, retaining both observations.
Missing claimed paths do not conflict with an actual matching copy elsewhere in
the explicit list. An incomplete pin always stays `UNPINNED`.

A match proves only observed byte identity. It does **not** verify manufacturer
origin, document revision, latest online version, PDF structure, license, visual
anchors, page labels, factual correctness, engineering suitability, human review
or canonical approval. It does not resolve source warnings or extend historical
owner acceptance. A successful command means the audit ran; exit status 0 does
not mean every row matched. Inspect `summary.local_byte_checks` and the rows.

## Safety, privacy and read-only limits

- Maximum 128 candidates, 64 MiB per file and 512 MiB combined; reads stream in
  at most 1 MiB chunks. A file that grows past a bound aborts after at most one
  detection byte beyond that bound, with no partial result.
- Candidates must be regular files. Symlinks, Windows reparse points, directories,
  FIFOs, sockets and devices are rejected, including symlink/reparse ancestors.
  UNC/device namespace roots and URL roots are rejected before cache access.
  Choose a genuine local directory; the tool cannot detect whether an OS-mounted
  filesystem or drive is backed by a network service.
- Root paths cannot be filesystem roots or contain traversal; root spelling is
  bounded to 4,096 characters and 128 components. Candidate paths
  reject absolute paths, traversal, empty components, backslashes, colons/alternate
  data streams and control characters; limits are 1,024 characters and 16 parts.
  No path normalization silently redirects a candidate. On systems where an
  ordinary temporary-directory spelling has a symlink ancestor, explicitly choose
  the real nonsymlink path instead.
- Every root ancestor and candidate directory is opened relative to its held
  parent descriptor with `O_DIRECTORY | O_NOFOLLOW`, from the filesystem anchor
  down. Candidate leaves use descriptor-relative `O_NOFOLLOW | O_NONBLOCK` opens.
  A path recheck alone is not relied on to prevent ancestor-symlink redirection.
  File identity/size/timestamps and held directory identities are compared before
  and after reading; changed associations fail closed. Descriptors are closed on
  success, missing files and errors. Local OS permissions remain the trust boundary;
  this is not protection against a filesystem that lies about identity/metadata,
  privileged mount changes or undetectable concurrent modification.
- Candidate paths are omitted by default. `--include-paths` includes only the
  caller-supplied relative paths, never the absolute cache root. These relative
  names can still be sensitive; inspect before sharing. Normal cache errors omit
  absolute paths. Hashes and byte counts themselves are observations, not secrets
  automatically cleared for publication.
- Output is JSON on stdout only. There is no output-file option, evidence import,
  package update, Git operation, directory creation or metadata mutation. Use `-B`
  to suppress ordinary Python import caches. Caller-selected stdout redirection
  is separate from the command. Read access timestamps can change at the OS level.

Invalid input, unsafe files, resource limits, changed files or invalid metadata
abort the whole command with exit status 2 and no partial stdout. Missing listed
files are observations, not fatal errors; a missing/invalid cache root is fatal.
There is no retry, fallback cache or search outside the selected inputs.

The Python API is
`pcbknowledge.git_native.intake_evidence_audit.intake_evidence_audit(root: Path,
*, cache_root: Path, cache_files: Sequence[str], include_paths=False,
source_id=None, manufacturer=None, device=None, package=None, revision=None) -> dict`.
The concrete candidate collection must be a bounded list or tuple.

## Verification

`tests/git_native/test_intake_evidence_audit.py` uses invented opaque bytes, not
third-party PDFs. It checks all five outcomes, duplicate copies, incomplete and
malformed pins, batch-local identity and exact filters, pathless output, unsafe
metadata hints, traversal/UNC/device roots, simulated symlinks/reparse/special
files, limits and growth, before-open replacement, same-size mutation, descriptor
cleanup, both CLI entrypoints, index/mode/mtime/cache immutability, workspace
validation and invalid unrelated metadata. The POSIX suite also attempts actual
ancestor swaps, checks descriptor cleanup and caps root depth before access.
Six portable tests cover matching/validation semantics and unsupported API/CLI
rejection with no cache access or mutation; 29 additional tests exercise actual
POSIX byte I/O. Unsupported platforms run the six portable tests, not skipped or
fake successful byte-audit cases. Independent review additionally probes actual
symlinks and FIFOs on a supporting OS. See the [read-only intake contract](read-only-intake.md)
and [recorded coverage inventory](intake-coverage.md) for metadata-only views.

Local Linux receipt (2026-10-28): all 35 dedicated audit tests and 117 focused
intake tests passed; Build and Test each passed 272 tests with no skips. All 114
pinned retrieval cases, Config, workspace/Agent validation, English/public/PDF.js
guards and metadata-only Package exited 0. Independent review passed the same
focused suites plus 13 semantic/static-path probes and four race/cleanup probes,
with no remaining blocker. The actual bounded local check compared 14 explicitly
listed candidates (27,861,283 bytes): 21 source scopes matched and one remained
unpinned, with no recorded metadata changes. These are local-byte observations,
not new content review or approval. Exact-commit remote CI, including macOS I/O
and Windows unsupported behavior, is checked separately after publication.
