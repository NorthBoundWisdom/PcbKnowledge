# Contributing to PcbKnowledge

Thank you for improving PcbKnowledge. The primary constraint of this project is not to collect as much material as possible; it is to keep engineering knowledge, licensing, evidence, dependencies, and human publication boundaries verifiable.

## 1. Do not submit production knowledge to the public source repository

The following content is not accepted in the public upstream by default:

- real `knowledge/sources/**`, `knowledge/entities/**`, or `knowledge/facts/**` authority data;
- datasheets, standards, internal documents, or other real `evidence/**` PDFs;
- internal company guidelines, reviews, waivers, or historical cases;
- credentials, tokens, private keys, production URLs, or identifiable internal infrastructure details;
- test fixtures you do not have the right to publish or redistribute.

The public upstream permits only the repository-defined `.gitkeep` placeholders under `knowledge/**` and `evidence/**`. `python3 configs/check_public_repo.py` enforces this contract.

Prefer synthetic fixtures for tests. If third-party material genuinely needs to be public, document its source, license, redistribution basis, exact version, and integrity information in the pull request and obtain explicit maintainer review.

## 2. Development boundaries

- Do not make PcbKnowledge a runtime dependency of PcbCore and do not mutate live PCB board state.
- Keep the current runtime loopback-only and Python-standard-library-first.
- Agents may prepare, edit, validate, and submit drafts, but may not approve, reject, stage, commit, or push.
- Unknown values, conflicts, wrong revisions, wrong packages, and license blocks must fail closed.
- Knowledge/evidence data commits must not be mixed with code, schema, policy, or documentation changes.
- The public software checkout and production knowledge workspace are separate repositories. Do not silently move data between them.
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
python3 configs/pcbknowledge_agent.py validate
```

For changes that affect package contracts, also run:

```bash
python3 configs/pcbknowledge_workflow.py package
```

For GUI changes, perform a real loopback smoke test. For visual evidence changes, open a representative Fact in a desktop browser and verify the exact Source page and bbox placement; HTTP/view-model tests alone do not prove pixel placement. A skipped, truncated, interrupted, or unexecuted check is not a pass.

## 4. Pull requests

Keep each pull request focused. Describe:

- which contract or behavior changed;
- why the change is necessary;
- which tests cover it;
- whether Source / Entity / Fact / EvidenceAnchor schemas are affected;
- whether the license gate, publication boundary, workspace boundary, Agent privileges, CSP, or vendored dependency contract is affected.

Do not make a fixture pass by weakening a validator, relaxing fail-closed policy, skipping tests, or mixing data with the policy that validates it.

## 5. Contribution license

Unless you explicitly designate a submission as "Not a Contribution" in writing, contributions intentionally submitted and accepted into this project are provided under the Apache License 2.0 terms applicable to the repository. Contributors must have the right to provide the submitted code, documentation, test material, and any third-party assets included in their submission.

Report security vulnerabilities privately according to [`SECURITY.md`](SECURITY.md).
