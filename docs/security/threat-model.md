# MVP threat model

## Assets and trust boundaries

Permanent source bytes, document revisions, evidence anchors, reviewed records, review decisions, license policy, identity mappings, and audit events are protected assets. Browsers, uploaded PDFs, extracted text, filenames, model output, and caller-supplied identifiers are untrusted.

Caddy is the public ingress. Keycloak is the identity authority. The API is the sole authorization boundary for domain and object access. PostgreSQL is the transactional authority and RLS is defense in depth. Workers receive bounded jobs but no board-write, arbitrary shell, GitHub, or authorization-bypass capability. SeaweedFS object keys are not bearer capabilities.

## Primary threats and controls

| Threat | Required control |
|---|---|
| Cross-project enumeration or retrieval | Authenticate and authorize before lookup/ranking; indistinguishable denial responses; RLS negative tests |
| Object-key bypass | Private S3 credentials; API-mediated reads; short scoped URLs only after authorization and audit |
| Prompt/document injection | Treat bytes/text as data; fixed tool policy; typed extraction; no model publication |
| Wrong MPN/package/revision | Exact hard filters before text ranking; explicit unknown/conflict states; golden negatives |
| Evidence tampering | Server-side SHA-256, immutable object key, revision-bound anchor, readback sampling |
| Review bypass | Separate curator/reviewer roles; ETag; atomic review/publication/audit transaction |
| Audit suppression | Append-only table; application role cannot update/delete; audited operation fails if audit write fails |
| Secret disclosure | Runtime secret mounts; no browser secrets; redacted structured logging; repository scanning |
| Parser exploit | MIME/magic/size checks; no-network constrained parser; read-only input; bounded CPU/memory/time |
| License-policy bypass | Policy check before parse/index/model/raw access; default licensed material blocked for AI |

Permanent-object write authority is not present in the long-lived API or
cleanup worker. The API can sign staging uploads and audited permanent reads;
the cleanup worker can delete staging keys only. The M2 verifier/promotion
boundary must be isolated, hash-derived, create-only in normal operation, and
covered by real-backend canonical-preservation tests before intake is enabled.

## Security verification gate

Required tests cover wrong issuer/audience/expiry, browser versus service-account permissions, two-project non-interference, object access without API authorization, restricted-license actions, audit atomicity, concurrent review, wrong entity/revision, malicious PDF actions/attachments, and log redaction. A skip or mock-only result is not a production-path pass.
