# ADR-013: Anchor evidence by page and normalized PDF coordinates

## Status

Accepted — 2026-08-08. Coordinate transform clarified for P0.3b on 2026-08-18 before production authority was introduced.

## Context

Engineering facts must open at exact source evidence across browser sizes and PDF zoom. Parser block IDs and pixels are tool/version dependent. A normalized coordinate space is only interoperable if its page box, rotation, origin, and axis direction are explicit.

## Decision

`EvidenceAnchor` uses a 1-based page number, coordinate space `PDF_NORMALIZED_V1`, and bbox values satisfying `0 <= x0 < x1 <= 1` and `0 <= y0 < y1 <= 1`. It binds one immutable document revision and records quote hash plus optional section/table coordinates.

`PDF_NORMALIZED_V1` is defined against the displayed PDF page after applying the page's intrinsic crop box and intrinsic rotation, equivalent to the page viewport returned by PDF.js for that page at any positive uniform scale:

- origin: top-left of the displayed page viewport;
- positive X: right;
- positive Y: down;
- `x0`, `x1`: horizontal positions divided by displayed viewport width;
- `y0`, `y1`: vertical positions divided by displayed viewport height;
- zoom/device-pixel ratio are not part of the coordinate identity;
- user-selected viewer rotation is not part of the coordinate identity.

A renderer therefore maps the normalized bbox directly onto the full displayed page viewport. P0.3b renders the canonical PDF page using its intrinsic rotation/crop and places a normalized SVG overlay over exactly that canvas. The overlay is a projection only and never rewrites the anchor.

The Source revision remains part of evidence identity through `source_id`; an anchor never follows a replacement Source automatically. Page/bbox/quote validity is fail-closed at the authority boundary, and PDF bytes are separately verified by Source evidence SHA-256/size/path.

## Alternatives

- Page number only.
- Pixel coordinates tied to one render.
- Extracted text offsets or parser node IDs only.
- Raw unrotated PDF user-space coordinates requiring every renderer to reproduce crop/rotation transforms.

## Consequences

The same anchor can be rendered at different browser sizes and device-pixel ratios without coordinate migration. P0.3b can use a renderer-independent normalized SVG overlay while PDF.js handles page crop and intrinsic rotation.

Future tests that use real PDFs should include non-zero intrinsic rotation and non-default crop boxes. If another extraction pipeline produces raw PDF user-space coordinates, that pipeline must convert them into `PDF_NORMALIZED_V1` explicitly and test the transform before writing authority.

## Rollback

Add a new versioned coordinate space and an explicit conversion receipt. Preserve original coordinates and Source revision; never silently reinterpret or rewrite historical anchors.
