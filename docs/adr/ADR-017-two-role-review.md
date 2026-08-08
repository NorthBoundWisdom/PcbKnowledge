# ADR-017: Separate curation from high-risk approval

## Status

Accepted — 2026-08-08.

## Context

Data operators can upload, normalize, anchor, and verify evidence efficiently, but pin and package facts can affect physical designs. A single role or model must not author and approve high-risk facts.

## Decision

`DATA_CURATOR` may prepare candidates and verify evidence. `DOMAIN_REVIEWER` must independently approve high-risk engineering facts before publication. Publication policy checks both decisions, evidence validity, authorization, ETag, audit, and unresolved conflicts. Models can only create candidates.

## Alternatives

- Allow curators to publish all records.
- Let a model publish above a confidence threshold.
- Require an engineer for every low-risk metadata edit.

## Consequences

High-risk facts have accountable separation of duties while metadata operations remain practical. Review queues and reviewer availability become operational concerns.

## Rollback

Risk classes may be refined through a superseding policy ADR, but removing independent approval for high-risk facts requires equivalent safety evidence. Existing review decisions and audit history remain immutable.
