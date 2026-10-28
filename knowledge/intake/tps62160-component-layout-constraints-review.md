# TPS62160 component and layout constraints: collection receipt

Current status: AGENT_REVIEWED_UNDER_OWNER_DELEGATION; see the independent receipt below. Collector history remains DRAFT, not self-acceptance.

Issue: https://github.com/NorthBoundWisdom/PcbKnowledge/issues/18
Base: `a7cdf346e29b76112b649d7a993e077b696be7fd`.
Collector: `agent:/root/curate_next_pcb_constraints/collect_buck_constraints`.
Collection: 2026-10-28 UTC. Only this new JSON/review pair is collector-owned;
aggregate replay, publication and CI belong to the integration owner under #16.

## Actual source and identity

Fresh official download: https://www.ti.com/lit/ds/symlink/tps62160.pdf .
Actual SHA-256: `abc824ca04ee985ede3a513172ccdd2a42c8e1fdcfc3af5acdbe2c1af31aaa72`.
Size: 2784747 bytes; 42 PDF pages. These match the previous `ti-tps62160`
receipt by measured bytes, not URL equality. Electrical revision SLVSAM2E,
May 2017; packaging addendum 10-Nov-2025 is distinct. No global-latest claim.
PDF page 30 / Addendum-Page 1 identifies TPS62160DSGR as WSON DSG, eight pins;
DGK and fixed 62161/2/3 rows are not this scope. Page 14 distinguishes the
adjustable TPS62160 from the fixed variants.

The original remains only in ignored local cache:
`.pcbknowledge/evidence/sha256/ab/abc824ca04ee985ede3a513172ccdd2a42c8e1fdcfc3af5acdbe2c1af31aaa72.pdf`.
Collector inspected actual renders of PDF pages 14, 15, 16, 26 and 30.
Printed/PDF numbers agree for the four technical pages. No precise bbox was
measured. Public reference does not mean open redistribution or canonical
source-processing clearance. No source PDF, extracted full text or image is
included in Git or delivery.

## Rendered Table 2 interpretation

Page 14 was inspected as a rendered page, not reconstructed from flattened text.
Checked cells: L=2.2 uH with C=10, 22, 47, 100, 200 uF; L=3.3 uH with
C=10, 22, 47, 100 uF. The 1 uH and 4.7 uH rows are blank, as are the
4.7 uF and 400 uF columns. The 3.3 uH / 200 uF cell is blank. The footnotes
identify nominal values with typically +/-20% variation assumed for tolerance,
saturation and DC bias; 2.2 uH / 22 uF is the standard recommendation.
A blank cell lacks this table's checked support, not proof of instability.
The annotation preserves only factual combinations and conditions in a new
representation; it is not an image or copied table layout.

## Scoped candidates and limits

Eight annotations cover the matrix, static peak-current/ripple guidance, L/PSM
tradeoff, output capacitor recommendation, input/effective-capacitance guidance,
loop/divider interaction, power-loop placement and feedback/ground routing.
Existing seven pin/supply records are referenced, not recopied. Three local
warnings retain missing actual component behavior/operating point, inductor
ratings and PCB/system evidence. No external application note or component
catalog was opened; no procurement choice, calculator, simulation or electrical
qualification is delivered.

The approximate 20% inductor-current margin is guidance, not a rating. Static
PWM equations do not certify startup/transient/fault peaks. The 22 uF output and
10 uF input recommendations do not establish universal minimum effective values.
The numeric ESR bound and a proposed board's thermal/stability margin are not
invented. Connecting the pad does not discharge the other layout constraints.

## Replay and expected selections

Run from the repository root. Each command below must exit 0. Results remain
noncanonical candidates with reader `NOT_LOCALLY_VERIFIED`; collection/review
status does not attest original bytes on the querying machine. Each positive
fact contains all three batch-local warnings. These commands select metadata,
not calculate or approve a proposed circuit.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter LC_checked_combinations
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter inductor_peak_current
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter inductance_mode_tradeoff
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter output_capacitor
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter input_effective_capacitance
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter loop_component_context
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter power_loop_placement
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --parameter feedback_ground_routing
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id buck-app-ti-e-dsg
```

The eight fact queries select `buck-app-01` through `buck-app-08`, respectively.
The issue query selects `buck-app-components-unknown`, `buck-app-current-unknown`
and `buck-app-layout-unknown`. For LC substitution use 01/04/05/06 plus warnings;
for current suitability use 02/03 plus warnings; for effective capacitance use
04/05 plus warnings; for layout sufficiency use 07/08 plus warnings.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --manufacturer 'Other vendor'
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --device TPS62161DSGR
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --device TPS62160DGKR
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id buck-app-ti-e-dsg --package 'DGK, 8-pin VSSOP'
```

All four identity negatives return `[]`; no source transfer or inferred package.
Semantic review cases are distinct from these exact filters: 3.3 uH/200 uF is
not a checked cell; nominal 22 uF does not prove biased effective capacitance;
load current is not an inductor saturation rating; a typical BOM does not
become a guaranteed operating bound; an unseen board cannot earn stability/EMI
or current qualification from a grounding lookup. No empty query is proof of
safety or absence of constraints.

## Collector checks, 2026-10-28 UTC

- Thirteen real CLI invocations above: exit 0; eight exact fact selections,
  one three-warning lookup and four empty identity negatives, no skips.
- Python assertions on the draft payload verified checked/unchecked cells,
  recommendation semantics, static-load conditions and warning retention.
- `python3 configs/check_english_repo.py`: exit 0.
- `python3 configs/check_public_repo.py`: exit 0.
- Full integrated tests, successor aggregate, Package, publication and CI are
  separate pending integrator gates; these focused checks do not claim them.

Draft JSON SHA-256 before independent review:
`543139ab29c094ffb24bbaf1ce22e99b905f36d45c0ea3cdbe0b53104c20902d`.
Independent evidence and final-payload review is recorded below; collector did not self-approve.

## Independent Agent review

Current status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**.
Reviewer: `agent:/root/curate_next_pcb_constraints/review_new_constraint_sources`; reviewed at `2026-10-28T03:29:20.891553+00:00`.
Original PDF hash independently recomputed; actual cited page renders, identity,
revision and all factual values/conditions/unknowns independently inspected.
No factual correction was necessary. Current evidence-method/status prose was
updated; historical DRAFT collection and unresolved engineering inputs retained.
This is delegated Agent review, not human acceptance, canonical clearance or
application qualification. No full original is published.

Reviewed draft JSON SHA-256: `543139ab29c094ffb24bbaf1ce22e99b905f36d45c0ea3cdbe0b53104c20902d`.
Reviewed final JSON SHA-256: `dd76bb3ba81a5684a46aaeca11ad06ac0af236660fcb8c0c776f94b534dc4eaa`.

Independent replay: all 13 commands in this receipt returned exit 0 and valid
JSON. A separate 44-case check of all new successor selections asserted exact
IDs, unchanged complete fact/issue payloads, all warning associations and
noncanonical/NOT_LOCALLY_VERIFIED markers; all passed. The four new regression
tests passed after final review pins and the explicitly reviewed PGND lexical
expansion were integrated. The initial regression run failed on a stale draft
SHA pin before that integration; no facts were altered to fit test output.
