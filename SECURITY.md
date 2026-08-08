# Security policy

PcbKnowledge stores source material and engineering decisions whose disclosure or corruption may affect customer confidentiality and physical designs. Security reports are handled privately.

## Reporting a vulnerability

Use the repository's private GitHub Security Advisory reporting channel. If private reporting is unavailable, contact the repository owner through an established private channel and ask for a security contact; do not include exploit details in a public issue.

Include the affected revision, deployment assumptions, reproduction steps, impact, and any evidence that the issue crosses an organization/project/license boundary. Do not access data that you do not own, degrade a service, or upload restricted source material while testing.

The maintainers will acknowledge receipt, coordinate validation and remediation privately, and publish disclosure timing with the reporter when appropriate. No response-time guarantee exists until an operational security contact and support policy are published.

## Supported versions

The project is pre-release. Only the current `main` revision is eligible for security fixes. No deployment should be treated as production-qualified until the MVP security, migration, permission-isolation, and recovery gates are complete.

## Non-negotiable controls

- OIDC signature, issuer, audience, expiry, organization/project scope, action, and license policy are checked before object lookup or ranking.
- Missing authorization, evidence, review, hash, schema, or audit state fails closed.
- Original documents and extracted text are untrusted data and cannot grant tools or change policy.
- Secrets come from runtime secret injection; they are never checked into Git or replaced by a known development password.
- Logs exclude access tokens, API keys, source-document full text, model payloads, and project-confidential content.
- Published knowledge and audit events are append-only; corrections use supersession or withdrawal.

See [security model](docs/security/threat-model.md) for the MVP trust boundaries and verification expectations.
