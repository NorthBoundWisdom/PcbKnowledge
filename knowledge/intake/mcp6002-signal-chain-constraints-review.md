# MCP6002 signal-chain constraints: collection and review receipt

Current review status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**; see the
[dated independent acceptance](#independent-agent-acceptance-2026-10-28-utc).
Earlier collector sections record historical DRAFT work, not current acceptance.
Coordinated aggregate integration/publication remains separate; no human or
canonical acceptance is asserted.

## Scope and ownership

Collector: `agent:/root/collect_opamp_application_knowledge`.
Collected 2026-10-28 UTC. This no-issue parallel slice owns only the adjacent JSON
and this receipt. The coordinator owns the aggregate evaluation manifest and
shared documentation. Seven new annotations address useful missing application
questions; annotation count is not an acceptance target.

Knowledge baseline: 125 annotations at public data commit `98113c3`, retained at
`24c63b0`. Collection/replay used local software checkout `ac277e8`; its presence
is not a claim of remote publication. The previous seven MCP6002 annotations and
all owner-accepted bytes remain unchanged. The earlier owner acceptance covers
only its pinned 100-record snapshot, not these additions.

## Actual source evidence

Official source: [Microchip DS20001733L](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP6001-1R-1U-2-4-1-MHz-Low-Power-Op-Amp-DS20001733L.pdf).
Revision L, March 2020, is identified on PDF/printed page 45. PDF/printed page 47
explicitly identifies MCP6002-I/SN as industrial, 8-lead SOIC; I grade is -40..85 C.
The part is not the T reel orderable, E grade, MSOP or DFN scope.

Cached original SHA-256:
`4f879ab31115ecfa149dfea62073c9efdbc4beccbdfc3a8d7e10281f3877f8fb`.
Byte size: 931340. Page count: 50. The collector recomputed actual cached bytes,
matching the prior `microchip-mcp6002-l` receipt; this was not a fresh download or
latest-revision check. Source originals are local-only, excluded from the pair,
Git and packages. Public availability is not a redistribution license or canonical
Source-processing authorization.

Collector inspected actual renders of pages **3, 4, 13, 14, 45 and 47**, not just
extracted text. PDF and printed page numbers agree. No precise bbox was measured.

| New ID | Parameter | Source anchors and retained boundary |
| --- | --- | --- |
| `mcp6002-app-01` | `input_common_mode_range` | p3 DC row/header; p13 sections 4.1.2/4.1.3. Nominal extension is not arbitrary fault permission; below-ground source current matters. |
| `mcp6002-app-02` | `input_stage_transition` | p13 section 4.1.3. Noninverting linearity guidance at input-stage crossover, without inventing a tolerance or forbidden-zone width. |
| `mcp6002-app-03` | `output_saturation_headroom` | p3 swing row plus p13 section 4.2. VOL maximum/VOH minimum at the stated load, supply and overdrive; not a linear-swing guarantee. |
| `mcp6002-app-04` | `gain_bandwidth_product` | p4 AC table/header. Typical 1 MHz only; minimum/maximum remain null. |
| `mcp6002-app-05` | `slew_rate` | p4 AC table/header. Typical 0.6 V/us only; minimum/maximum remain null. |
| `mcp6002-app-06` | `capacitive_load_isolation` | p14 section 4.3 and figures 4-3/4-4. Noise-gain normalization, feedback before isolation, example load guidance and required response checks; no universal capacitance or resistor value. |
| `mcp6002-app-07` | `supply_bypass_placement` | p14 section 4.4. Local and bulk capacitance/placement guidance, not board power-integrity certification. |

The source's page 14 unused-amplifier section explicitly targets MCP6004. No
MCP6002 unused-channel circuit was inferred. Industrial grade does not expand
TA=25 C electrical entries to guaranteed full-temperature performance. The AC
phase-margin row's G=+1 condition was not silently applied to the GBWP/slew rows.

Three batch-local warnings preserve missing signal-envelope, dynamics and sensor
inputs. They do not become Facts or a recommendation. No sensor impedance limit,
load current allowance, guaranteed full-power bandwidth, isolation resistor,
complete protection network or automatically fitted circuit is supplied.

## Bounded questions and replay

Use the real read-only CLI from the software checkout with an explicit selected
workspace. Replace `<workspace>` with the reviewed workspace; the collector used
a separate initialized temporary Git workspace containing this pair and the
unchanged cross-manufacturer baseline. In an integrated checkout it can be `.`.

Each search below selects one corresponding new ID, in table order:

```bash
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter input_common_mode_range
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter input_stage_transition
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter output_saturation_headroom
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter gain_bandwidth_product
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter slew_rate
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter capacitive_load_isolation
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter supply_bypass_placement
python3 configs/pcbknowledge_agent.py --repo <workspace> intake issues --source-id mcp6002-app-microchip-l-sn
```

Warning IDs, sorted by the reader:
`mcp6002-app-dynamics-unknown`, `mcp6002-app-envelope-unknown`,
`mcp6002-app-sensor-unknown`.

1. **Can a nominal 6 V or near-rail signal be accepted without more conditions?**
   Retrieve `app-01/03` plus all warnings and the existing supply/stress records:

   ```bash
   python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id microchip-mcp6002-l --parameter supply_voltage
   python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id microchip-mcp6002-l --parameter VDD_minus_VSS
   ```

   These select `b002-microchip-mcp6002-l-05/04`, respectively. The operating record
   retains the November-2007 screening note and 1.8/5.5 V min/max measurement
   caveat. The 7 V stress limit is not operating permission. Supply tolerance,
   date code, temperature, input trajectory and output load remain required.
2. **Does 1 MHz GBWP mean a guaranteed 1 MHz signal path at any gain?** Retrieve
   `app-04/05/06`. No: typical GBWP/slew are not guaranteed minima or a gain/load
   response certificate. Amplitude, noise gain, load and settling requirements
   remain unresolved; the reader does not calculate applicability.
3. **Is a unity-gain sensor buffer automatically stable with a cable or ADC load?**
   Retrieve `app-01/02/06/07` plus all warnings. No capacitance limit or RISO is
   chosen; actual load dynamics, source impedance and required precision need
   independent circuit assessment. A bypass recipe alone is not validation.
4. **Can the stated output reach either rail linearly?** Retrieve `app-03` and
   the envelope warning. The stated swing endpoints use 0.5 V overdrive and a
   10 kohm midpoint load at 5.5 V; they do not establish precision linear output
   at the rail or at a different load/supply.

Each following exact-filter query must return an empty candidate list, not a
fallback or a declaration that the alternative device is electrically unsuitable:

```bash
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --device MCP6001-I/SN
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --device MCP6002-E/SN
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --device MCP6002T-I/SN
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --manufacturer 'Texas Instruments'
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --package '8-lead MSOP'
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --package '8-lead 2x3 DFN'
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --kind guaranteed_minimum
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --source-id mcp6002-app-microchip-l-sn --parameter maximum_stable_load_capacitance
```

A changed revision also requires new evidence; there is no revision filter in this
CLI and no invented command. Typical-only, wrong-load, full-temperature and
unspecified-circuit questions are semantic exclusions inspected against retained
conditions, not claims of an electrical-answer engine. Empty search results cannot
prove electrical permission or absence of unknowns.

## Historical collector verification (DRAFT stage)

- Seven parameter queries, warning query, two existing-record references and
  eight exact-filter negatives: **18 cases passed**, each CLI exit 0.
  Every positive retained the complete fact/source/warnings payload and
  `canonical: false`, DRAFT acceptance and `NOT_LOCALLY_VERIFIED` marker.
  Recorded visual checks do not upgrade the reader's local-byte status.
- `PYTHONPATH=src:. python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`:
  exit 0, **67 tests**, no skips, 4.675 seconds, on local software `ac277e8`.
  These synthetic tests cover the implementation, not source factual accuracy.
- A first replay helper used `issue` instead of the CLI's `source_issue` field;
  it stopped with KeyError. The helper was corrected and all 18 cases reran.
- A CLI help probe without explicit `--repo` was refused with INVALID_WORKSPACE;
  it is not a passing validation. All substantive replays selected the temporary
  workspace explicitly.
- Full aggregate evaluation, Build/Test/Package, staged publication guards,
  commit, push and exact-commit CI are coordinator-owned and not yet claimed.

## Historical independent-review handoff

Independent reviewer must inspect actual pinned bytes and rendered pages, verify
all numerical/condition scopes, replay the full payloads and negatives, then
provide actual Agent identity/time and reviewed-input SHA-256. Until that decision,
DRAFT remains unchanged and no owner/human acceptance is implied.

## Pre-acceptance correction and additional collector checks

Independent reviewer `agent:/root/verify_opamp_application_evidence` requested
explicit `VOL_max_expression` / `VOH_min_expression` strings because a
"minimum below-rail gap" key could invert the intended high-output bound. The
collector changed only that representation and added the DC-header
`VCM=VDD/2` condition. The dynamics warning now also cites the p4 AC table.
The original DRAFT digest is retained in append-only JSON review history.

The collector staged only this new pair in its isolated replay workspace and
called the production `check_public_distribution` and `check_english_repository`
functions: exit 0, no violations. Agent `validate` also exited 0 with
METADATA_CLOSURE VALID, 2 intake batches and zero canonical records. These
limited checks do not replace the coordinator's final staged aggregate guards.

## Independent Agent acceptance (2026-10-28 UTC)

Reviewer: `agent:/root/verify_opamp_application_evidence`, distinct from collector.
Actor type: AGENT. Authority: OWNER_DELEGATION. Decision:
AGENT_REVIEWED_UNDER_OWNER_DELEGATION. Review time: `2026-10-28T03:25:13Z`.
This supersedes the historical pending-review handoff, not its provenance.
`canonical: false` and `human_reviewed: false` remain unchanged.

Reviewed corrected DRAFT JSON SHA-256:
`dacec5538e2fcef6c00ee0fd2727249f2fa055f077852ac1f0712980a9c020ef`.
Reviewed DRAFT receipt SHA-256:
`78e43d4b044280f4f7649dfdd369ee51c6a39d9541ee26447f52b46024b6eb65`.

The reviewer independently verified actual cached source hash, byte count and
page count, then inspected actual rendered pages 3, 4, 13, 14, 45 and 47. All
seven numerical/conditional scopes and all three warnings passed. Output
VOL/VOH direction, VCM header condition and the dynamics warning's additional
p4 citation were verified after correction. Existing accepted records were not
duplicated. Typical values, industrial grade versus TA=25 C entries, wrong
orderables/packages, unknown circuit inputs and the MCP6004-only unused-channel
example remain properly bounded.

Independent real-CLI replay against a frozen 125-record baseline: **27 cases
passed**, preserving full facts, sources and warning payloads: seven parameter
queries, one warning query, one all-source query, fourteen identity-negative
search/issues queries, two unsupported guarantee-field queries and two retained
baseline supply/stress queries. Every candidate remains noncanonical and the
reader still reports NOT_LOCALLY_VERIFIED. The reviewer also ran
`PYTHONPATH=src:. python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`:
exit 0, **67 tests**, zero skips, 4.829 seconds. This acceptance does not approve
aggregate integration, publication or circuit design.

## Standalone handoff gates on public base a7cdf346

The final accepted JSON is:
`545a56afa94c48629e199ae072997fb78ab9ae9b54684b66b5c9b2568f7b5f7b`.
Post-status independent review reran all 27 full-payload CLI cases: PASS. Current
reviewer provenance, methods, status and history were checked without new source
or semantic changes.

A separate checkout of public base
`a7cdf346e29b76112b649d7a993e077b696be7fd` was used; only this new pair was
added/staged. Before adding it, the unchanged aggregate command passed all
**70 cases** (64 base and 6 disposition cases), eight batches and 125 facts:

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . --cases evals/intake-retrieval-125.json --dispositions evals/intake-dispositions-2026-10-28.json
```

With this pair added, the same command exited **2**, correctly refusing the
changed batch set/bytes. This is an expected unresolved integration gate, **not**
a full aggregate pass; the manifest was not changed or weakened. The combined
workspace contains nine batches / 132 annotations, still noncanonical.

The following commands on the added-pair checkout exited 0:

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/check_pdfjs_vendor.py
python3 configs/pcbknowledge_workspace.py validate .
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py --repo . validate
python3 configs/pcbknowledge_workflow.py package
git diff --cached --check
```

Build passed **218 tests**, no skips, in 24.930 seconds. Test passed **218 tests**,
no skips, in 24.385 seconds. Validation remained METADATA_CLOSURE VALID with zero
canonical records. Package inspection confirmed exactly 15 members: nine intake
JSONs, one unchanged disposition, the workspace manifest, three schemas and its
derived manifest. The packaged new JSON matched the final SHA-256 above. No
original PDF, page render or extracted source text was packaged.

Publication boundaries: this standalone two-file delivery is for the coordinator's
coherent aggregate integration; it must not be pushed directly to main while the
pinned aggregate refuses it. No branch-ref update, merged aggregate, cross-platform
remote CI result or engineering qualification is claimed by this receipt. Final
aggregate pins, shared documentation, publication and exact-commit CI belong to
the coordinator.
