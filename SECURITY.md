# Security policy

## Supported product boundary

The supported surface is the pre-release PcbKnowledge implementation on `main`. The runtime is a local, loopback-only Python editor with no shared account system, remote clients, public database, or object store. Do not expose the editor port to a LAN, VPN, container bridge, or the public internet.

Local operating-system file permissions and the selected knowledge Git repository define the current access boundary. Git authorship and history provide engineering attribution, not strong authentication or cryptographic non-repudiation. Any future shared online deployment requires a new threat model and an explicit architecture decision before implementation.

## Non-negotiable controls

- Invalid or missing schema, source, revision, license, evidence digest, or review state fails closed.
- PDF originals are content-addressed from their actual bytes and are never silently overwritten.
- Committed `APPROVED` authority is immutable; corrections use a new record plus `supersedes`.
- PDF and extracted text are untrusted data. They cannot grant tools, change prompts, or relax review policy.
- Mutation routes retain loopback Host/Origin validation, CSRF protection, and optimistic revision tokens.
- Neither the GUI nor Agent CLI performs Git writes. The Agent CLI exposes no approve/reject operation.
- `UNKNOWN`, `RESTRICTED`, and `LICENSED_BLOCKED_FOR_AI` Sources fail closed for Agent/model processing.
- The public software checkout must not become the production knowledge authority.

## Public repository and supply-chain boundary

The open-source upstream separates software from production knowledge:

- tracked `knowledge/**` and `evidence/**` content in the public source repository is limited to approved empty-directory placeholders;
- `configs/check_public_repo.py` verifies that contract in CI;
- repository-facing text is kept English and `configs/check_english_repo.py` rejects CJK/Kana/Hangul text in tracked UTF-8 source files;
- ordinary pull requests do not receive project secrets and workflows default to `contents: read`;
- pull requests, issues, commit messages, fixtures, and PDFs are treated as untrusted external input;
- internal material, unauthorized third-party originals, tokens, keys, and production credentials must never be added to Git history or Actions artifacts.

`PUBLIC_REFERENCE` means that a source is publicly accessible; it does not grant PcbKnowledge permission to redistribute the source. Third-party material remains subject to its own license, independently of the Apache-2.0 software license.

## Reporting a vulnerability

Prefer GitHub **Private vulnerability reporting / Security Advisory** for this repository. If that channel is unavailable, use an established private contact with a maintainer. Do not first open a public issue or include exploit details, real secrets, or unpatched attack samples in a public pull request.

Include the affected revision, runtime-boundary assumptions, a minimal reproduction, impact, and any known mitigation. Do not access data or systems you are not authorized to access.

## Repository visibility and rewritten history

Changing a private repository to public exposes reachable Git history and relevant Actions history, not only the current working tree. Before a visibility change:

1. audit reachable history for secrets, internal identifiers, and third-party copyrighted material;
2. revoke or rotate any secret that ever entered Git history before attempting history cleanup;
3. inspect branches, tags, pull-request refs, Actions logs, and artifacts that may retain sensitive references;
4. understand that a public-source guard prevents new production knowledge from entering future commits but does not erase previously hosted Git objects.

The current repository history was intentionally rewritten before public release. If an old unreachable object contained an actual credential or other high-risk secret, treat that as a credential incident and follow GitHub's sensitive-data removal process rather than assuming a force-push erased the server-side object.

Recovery and publication rules are documented in [`docs/open-source-boundary.md`](docs/open-source-boundary.md).
