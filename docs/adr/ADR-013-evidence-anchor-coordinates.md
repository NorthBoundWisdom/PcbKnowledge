# ADR-013: Anchor evidence by page and normalized PDF coordinates

## Status

Accepted — 2026-08-08.

## Context

Engineering facts must open at exact source evidence across browser sizes and PDF zoom. Parser block IDs and pixels are tool/version dependent.

## Decision

`EvidenceAnchor` uses a 1-based page number, coordinate space `PDF_NORMALIZED_V1`, and bbox values satisfying `0 <= x0 < x1 <= 1` and `0 <= y0 < y1 <= 1`. It binds one immutable document revision and records quote hash plus optional section/table coordinates. The server validates page and revision consistency.

## Alternatives

- Page number only.
- Pixel coordinates tied to one render.
- Extracted text offsets or parser node IDs only.

## Consequences

PDF.js overlays are renderer-independent and evidence remains inspectable. Rotation/crop-box transforms and quote drift need explicit tests; anchors never auto-migrate to a new revision.

## Rollback

Add a versioned coordinate space and conversion receipt. Preserve original coordinates and source revision; never silently rewrite historical anchors.
