# Contributing to PcbKnowledge

Thank you for improving PcbKnowledge. The project exists to let a design brief become a manufacturable board ([ADR-022](docs/adr/ADR-022-board-generation-knowledge.md)). Contributions should serve the active stage in [`TODO.md`](TODO.md) or a [golden design](docs/golden-designs.md), while keeping licensing, evidence and publication boundaries verifiable.

## 1. Publish processed metadata, never source originals

The following content is not accepted in the public upstream by default:

- private or unvalidated material presented as canonical authority;
- datasheets, standards, internal documents, or other real `evidence/**` PDFs;
- internal company guidelines, reviews, waivers, or historical cases;
- credentials, tokens, private keys, production URLs, or identifiable internal infrastructure details;
- test fixtures you do not have the right to publish or redistribute.

Small original summaries, structured values with citations and metadata are permitted under [ADR-021](docs/adr/ADR-021-lightweight-curation-local-evidence.md) and ADR-022. The retired intake is available only in Git history. `python3 configs/check_public_repo.py` checks tracked and staged content; no raw documents or oversized knowledge payloads are allowed.

Prefer synthetic fixtures for tests. If third-party material genuinely needs to be public, document its source, license, redistribution basis, exact version, and integrity information in the pull request and obtain explicit maintainer review.

## 2. Development boundaries

- Do not make PcbKnowledge a runtime dependency of PcbCore and do not mutate live PCB board state.
- Keep the current runtime loopback-only and Python-standard-library-first.
- Agents may verify records (`AGENT_VERIFIED`) and use the authorized main-branch publication workflow. Never record a human verifier who did not act.
- Unknown values, conflicts, wrong revisions, wrong packages, and license blocks must fail closed; generation refuses rather than guesses.
- Canonical knowledge data commits must not be mixed with code, schema, policy, or documentation changes.
- Explicit workspace selection remains mandatory. Private data stays in controlled workspaces; original PDFs stay in ignored local caches and never enter packages.
- Repository documentation, UI text, comments intended for contributors, and public test fixtures must remain English. `python3 configs/check_english_repo.py` enforces this for tracked UTF-8 text.
- Third-party runtime assets are not ordinary source files: version, license, supply-chain origin, and exact committed hashes must remain reviewable. Do not replace vendored bytes manually without updating and validating the owning contract.

See [`AGENTS.md`](AGENTS.md), [`docs/architecture.md`](docs/architecture.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and [`docs/open-source-boundary.md`](docs/open-source-boundary.md) for the full repository contract.

## 3. Local verification

At minimum run:

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/check_pdfjs_vendor.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py --repo . v2 validate
```

For changes that affect package contracts, also run:

```bash
python3 configs/pcbknowledge_workflow.py package
```

For GUI changes, perform a real loopback smoke test. For visual evidence changes, open a representative part in a desktop browser and verify the exact cited source page; HTTP/view-model tests alone do not prove pixel placement. A skipped, truncated, interrupted, or unexecuted check is not a pass.

## 4. Pull requests

Keep each pull request focused. Describe:

- which contract or behavior changed;
- why the change is necessary;
- which tests cover it;
- whether knowledge schemas or registries are affected;
- whether the license gate, publication boundary, workspace boundary, Agent privileges, CSP, or vendored dependency contract is affected.

Do not make a fixture pass by weakening a validator, relaxing fail-closed policy, skipping tests, or mixing data with the policy that validates it.

## 5. Contribution license

Unless you explicitly designate a submission as "Not a Contribution" in writing, contributions intentionally submitted and accepted into this project are provided under the Apache License 2.0 terms applicable to the repository. Contributors must have the right to provide the submitted code, documentation, test material, and any third-party assets included in their submission.

Report security vulnerabilities privately according to [`SECURITY.md`](SECURITY.md).
