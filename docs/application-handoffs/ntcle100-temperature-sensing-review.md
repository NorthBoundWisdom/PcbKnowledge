# NTCLE100 application-input card: independent review

- Author/publisher: Agent `/root/document_ntc_application_inputs`.
- Distinct reviewer: Agent `/root/document_ntc_application_inputs/review_ntc_application_card`.
- Review completed: `2026-10-29T00:23:36.919109+00:00`.
- Result: **PASS**, no card correction required.
- Reviewed [card](ntcle100-temperature-sensing.md) SHA-256:
  `b10ff168fbd107b060601e824f40f02e2bddcb8d4102a7d0ed1e8d44c129bf81`.
- Clean detached technical snapshot: `67e02cef0edc6c67a8e2445c567afff8febe0ddd`.
- Separately replayed clean detached drafting base: `0a2de5daf023de3f770299cca8d3ab3fe5a0973a`.
- Source JSON SHA-256 at both snapshots:
  `085793b239cb1a67f455f327c7214fa87b5ffbb3df0161eaee72e34d8d514a5a`.

The reviewer independently read the complete source JSON and historical review,
then compared every full fact dictionary (`ntcle100-sense-01` through `07`),
source metadata, conditions, provenance and attached warnings against retrieval.
The three complete warning payloads were compared by ID, not order or count;
their full descriptions, status and provenance also remain in the card.
All results retain `canonical: false`, `human_reviewed: false` and
`NOT_LOCALLY_VERIFIED` semantics.

All five literal commands in the card were executed independently on both clean
snapshots, each exit 0. Their UTF-8 command hashes and complete stdout hashes
were recomputed, including stdout's final newline. Results at both commits:

| Recipe | Full stdout SHA-256 |
|---|---|
| Source search, seven full fact candidates | `2ba3d15e628c7d4e5c2b59fcf8f7d67b51667fb49904de8197342f61314dbab1` |
| Source issues, three full warnings | `a94b9955d85c13a55e6b577b5660241f23173598048c5ae3f6e61b241d8fdd24` |
| Wrong A suffix, wrong G tolerance/orderable, wrong 0603 package (each) | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

Each negative is independently justified by exact structured identity: selected
JB0 is not JB0A; J is not G; a radial bead is not 0603. Empty scoped results
are not global evidence absence, compatibility, incompatibility or safety.

Full-card review checked separate R25/Beta tolerances; zero-dissipation scope
and nonzero self-heating; conditioned 500-mW entry and unextended plot points;
7 versus excluded 8.5 mW/K; oil response versus unspecified-medium time constant;
strict voltage bound; coating/potting/unaudited handling limits; unresolved BMAX
notation; and exact no-A identity without substitution or lifecycle claims.
The single divider case labels invented nominal values, retains actual operating
and error-budget unknowns, and grants no temperature accuracy, response,
lifetime, component selection or circuit-safety qualification.

This is a new Agent documentation/retrieval review, not a new original-PDF or
HTML byte audit, visual inspection, human approval or canonical acceptance.
Historical PDF hash and source-review provenance are not promoted to new checks.
No original document, extract, image or private board input was retrieved or
published by this review. Repository gates, remote SHA/tree readback and terminal
exact-commit CI are the publisher's separate delivery evidence in
[issue #34](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/34);
this receipt does not assert those stages already passed.
