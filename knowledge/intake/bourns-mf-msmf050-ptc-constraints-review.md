# Bourns MF-MSMF050-2 PTC constraint review

- Status: AGENT_REVIEWED_UNDER_OWNER_DELEGATION; noncanonical, not human approval.
- Collector: `agent:/root/resume_compact_evaluation/curate_fuse_constraints`.
- Independent reviewer: `agent:/root/resume_compact_evaluation/curate_fuse_constraints/review_bourns_ptc`.
- Reviewed at: `2026-10-28T21:57:33Z`.
- Reviewed draft SHA-256: `28a842420852c6910212ddda3eaa0431c2c0f96315bb729b28662331bbb8f41f`.
- Accepted JSON SHA-256: `e9f8629bc2504c1999be2512248a51ffabeeb37ec2c4d99b8ec62c405ce48835`.

## Source and examination

Official source: https://www.bourns.com/docs/product-datasheets/mf-msmf.pdf

Actual local PDF SHA-256: `50d80228581842471d563e28ba0f1b67ab095ee95dfac4079f4a49f7f7bbf3c8`;
1,327,051 bytes, 16 pages. Both Agents rendered and visually inspected cited
pages 1, 3, 9, 11, 14 and 15. Reviewer independently read legal page 16,
recomputed byte identity and reviewed every field of seven facts and three warnings.
No reviewer live-download reattestation or measured bounding boxes are claimed.

The electrical series revision is BE, 09/26 (page 14), not an invented exact day.
Application notice 12/18 and legal appendix K2540 08/26R are separate revisions.
The source PDF, extracts and renders remain local only, outside Git and packages.

## Review result

All seven facts accepted without numerical correction. Exact base-model NRND
triangle was visually verified; text extraction alone misses it. The -2 suffix
means tape/reel per EIA-481, in the 2,000-piece group. No inventory claim follows.
The batch is useful for legacy-part assessment, not a new-design recommendation.

Hold and trip values retain 23 C; the maximum 0.15-second trip time requires the
8 A test at Vmax in still air. Neither 1 A trip current nor 100 A Imax is a
continuous-load allowance. Selected derating points use the base model, not an
X-suffix model. Tripped dissipation is typical, not a zero-current guarantee.
AC/DC designation, residual current, recovery timing and application-specific
fault/thermal qualification remain unknown. No mains, battery or system safety
certification is granted by this record.

## Rights and authority

The collector checked the official legal landing page
https://www.bourns.com/legal/disclaimers-terms-and-policies and the source legal
appendix; the reviewer independently checked that appendix. No explicit ban on
this limited original-annotation scope was identified. This is not an open license
or permission to redistribute source originals. Only original annotations and
small factual metadata are retained under ADR-021 and owner delegation.

Acceptance is Agent curation, not canonical Fact approval, a human signature,
or qualification of a circuit. Ordinary retrieval remains NOT_LOCALLY_VERIFIED
unless authorized local source bytes are actually verified.
