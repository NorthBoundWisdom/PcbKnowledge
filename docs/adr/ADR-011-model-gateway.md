# ADR-011: Mediate models through ModelGateway

## Status

Deferred — model-assisted processing is outside the first MVP.

## Context

Future extraction may use local or external models, while source licenses and confidentiality policies differ by document. Direct provider calls would scatter policy and audit enforcement.

## Decision

Any future model use goes through a typed ModelGateway that enforces data classification, provider/model/version, prompt/schema hashes, `store=false` where supported, budgets, timeouts, audit metadata, and structured output validation. It cannot publish facts or grant tools.

## Alternatives

- Call providers directly from modules.
- Standardize on one hosted model.
- Adopt a general agent/RAG framework as the policy layer.

## Consequences

Model use becomes reviewable and replaceable, at the cost of a deliberate adapter and policy matrix. The MVP remains fully functional without a model or API key.

## Rollback

Disable all providers and retain manual/heuristic candidate entry. Model-derived candidates remain unpublished unless independently evidenced and approved; derivative outputs may be rebuilt or removed.
