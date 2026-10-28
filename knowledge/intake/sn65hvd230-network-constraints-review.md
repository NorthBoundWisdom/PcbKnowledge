# SN65HVD230DR network-constraint collection receipt

Current status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**, as recorded below.
Historical collector status was DRAFT.
Issue #16; collector `agent:/root/curate_next_pcb_constraints/collect_can_constraints`.
Base `a7cdf34` on main, collected 2026-10-28 UTC. The collector owns only this
receipt and `sn65hvd230-network-constraints.json`; aggregate integration is separate.
Noncanonical, not human-reviewed and not CAN compliance or circuit sign-off.

## Actual source evidence

Official source: https://www.ti.com/lit/ds/symlink/sn65hvd230.pdf . Fresh acquisition
succeeded; 812,033 bytes, SHA-256
`e98fc0c59168c035d7958111924dae7e21e46ab45bdfd6400aef048299d6d716`.
The actual bytes match the prior interface-batch receipt. Electrical revision is
SLOS346O, April 2018; packaging addendum separately dated 5 March 2026.
PDF page 36 identifies SN65HVD230DR, D 8-pin SOIC, -40..85 C. No latest-revision
or procurement guarantee is made. Only this official source was consulted.

The original is local-only in
`.pcbknowledge/evidence/sha256/e9/e98fc0c59168c035d7958111924dae7e21e46ab45bdfd6400aef048299d6d716.pdf`.
`PUBLIC_REFERENCE` does not assert open redistribution rights. This is the
owner-authorized noncanonical factual-curation lane, not canonical license
clearance. No original PDF, full extracted text or page image is delivered.

Collector inspected actual rendered PDF pages 5, 6, 7, 8, 9, 15, 16, 17, 22, 26,
27, 28, 31, 32 and 36, plus text. Electrical printed pages equal PDF pages; page
36 is Addendum-Page 1. Ignored review aids are `.pcbknowledge/can-review/pN.png`
and `source.txt`. Rendering exited 0; nonfatal font-cache warnings were emitted.
Actual images were viewed rather than treating render completion as visual proof.
No precise bounding box was measured.

- 5/15: stress versus operation and Figure 24 pulse duration/duty/series resistor.
- 6/7/16/31: common-mode, individual-pin and differential ranges, receiver
  threshold columns and Table 1 context. No Table 1 test row is used to expand
  the general section 8.3 operating envelope.
- 8/17: ordered RS loop-delay columns and Figure 26 load/pulse/threshold setup.
- 9/16/22: 230 wake row, actual Figure 25 timing and receiver-active standby;
  231 receiver-off sleep is not transferred.
- 26/27/28: end termination/removal, resistor fault-power warning and explicitly
  typical cable-delay tradeoff, not an allowed network length.
- 32/36: supply-decoupling guidance and exact orderable/package identity.

Eight annotations `can-app-01` through `can-app-08` and three batch-local warnings
cover the bounded questions. Existing `b003-ti-sn65hvd230-o-01` through `-06` are
referenced for pins, supply and mode observations, not recopied or modified.

## Replay recipes and expected results

Run from the repository root. Every fact selection retains the full original
conditions, source, all three warnings, `canonical: false` and
`NOT_LOCALLY_VERIFIED`; the reader does not rehash source bytes.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter termination_placement
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter termination_resistor_fault_rating
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter receiver_common_mode
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter bus_stress_not_operation
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter slope_control_loop_delay
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter standby_wake_time
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter slope_cable_tradeoff
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --parameter local_supply_decoupling
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id can-app-ti-slos346o-d
```

Expected fact IDs in command order: `can-app-01` through `can-app-08`.
Expected warning IDs: `can-app-ground-fault-unknown`, `can-app-timing-unknown`,
`can-app-topology-unknown`. Filter-only issue retrieval avoids accidental lexical
omission; no-match results never prove absence of ambiguity.

1. Where should termination be placed if a node can be unplugged? Select -01/-02
   plus warnings. End termination stays on the bus, not on every node or on a
   removable endpoint without another arrangement. Actual topology/fault power
   remains unknown, not validated by the 120-ohm recipe.
2. Does a transient rating authorize continuous common mode? Select -03/-04.
   Operating common mode -2..7 V is distinct from bus stress -4..16 V and the
   +/-25 V, 100-ohm, 15-us, 1%-duty test. Actual ground offset, bias and noise
   must fit the relevant limits together; no fault-environment guarantee results.
3. Can slope control/standby meet a requested rate and wake deadline? Select
   -05/-06/-07 plus warnings. RS-specific maxima and load/test conditions survive;
   typical cable examples do not become guarantees. The 230 receiver remains
   active, and controller reactivation is required; no 231 sleep semantics apply.
   Controller sample point/cable delay/wake scheduling are still unspecified.

Identity exclusions (each exact selection must be empty):

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --device SN65HVD231DR
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --device SN65HVD232DR
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --manufacturer Nexperia
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id can-app-ti-slos346o-d --package 'DGK, 8-pin VSSOP'
```

Semantic exclusions are conditions/warnings, not a new circuit-analysis engine:
receiver-off standby, stress-to-operation, headline-rate-to-network qualification,
and typical-to-guaranteed transfer must remain disallowed in the selected payload.
Changing a warning or condition to approve such a case is not an acceptable
aggregate expected-output refresh.

## Collector checks and handoff

Independent source/payload review and provenance are recorded below; focused
CLI replay remains separately reported.
Do not erase this historical DRAFT receipt. Integration owner handles successor
aggregate, staged guards, final full gates, metadata-only package, remote SHA and CI.
No publication, independent acceptance or final CI is claimed here.

Collector checks completed before handoff: 13 CLI cases passed (eight complete
fact payloads with source/warnings, four identity negatives and one all-warning
lookup), exit 0. The initial private helper incorrectly assumed warning list order,
then the issue-result field name; these two assertion/helper failures preceded the
corrected pass and did not change data or reader code.
`PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`
exited 0: 67 tests, zero failures/errors/skips, 12.709 seconds.
`python3 configs/check_english_repo.py` and `python3 configs/check_public_repo.py`
each exited 0. Untracked additions still require the integrator's staged guard.
The enlarged batch set is not claimed to pass the historical pinned 125 manifest;
a coherent successor aggregate is required, without rewriting historical pins.

## Independent Agent review

Current status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**.
Reviewer: `agent:/root/curate_next_pcb_constraints/review_new_constraint_sources`; reviewed at `2026-10-28T03:29:41.390524+00:00`.
Original PDF hash independently recomputed; actual cited page renders, identity,
revision and all factual values/conditions/unknowns independently inspected.
No factual correction was necessary. Current evidence-method/status prose was
updated; historical DRAFT collection and unresolved engineering inputs retained.
This is delegated Agent review, not human acceptance, canonical clearance or
application qualification. No full original is published.

Reviewed draft JSON SHA-256: `64248bdee162d4cf89820145e08f5314991716ab6866c40dba6f5742181c87a6`.
Reviewed final JSON SHA-256: `5d63ded5fe37e892135b916bcd3ff2f7ca905ae28a85b37417d0856969300cb8`.

Independent replay: all 13 commands in this receipt returned exit 0 and valid
JSON. A separate 44-case check of all new successor selections asserted exact
IDs, unchanged complete fact/issue payloads, all warning associations and
noncanonical/NOT_LOCALLY_VERIFIED markers; all passed. The four new regression
tests passed after final review pins and the explicitly reviewed PGND lexical
expansion were integrated. The initial regression run failed on a stale draft
SHA pin before that integration; no facts were altered to fit test output.
