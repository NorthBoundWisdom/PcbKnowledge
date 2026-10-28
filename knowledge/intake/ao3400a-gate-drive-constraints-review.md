# AO3400A gate-drive constraints: collection and review receipt

Current status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**; see the independent
receipt below. Collector history remains DRAFT, not self-acceptance. This is a new
noncanonical discrete-MOSFET slice, separate from the published 162-record
signal/logic aggregate; its manifest has not been changed. No existing batch bytes or shared manifest were changed.

Collector: `agent:/root/collect_mosfet_drive_constraints`.
Collected 2026-10-28 UTC. Only this JSON/review pair is intended for eventual Git
publication; source originals, extracted text, renders, scripts and test logs are
local working evidence, not repository deliverables.

## Gap, exact source and visual evidence

The inspected baseline contains 148 IC-focused annotations. The separately
pending MCP6002/SN74HC00 slices are also ICs; no AO3400A source or discrete-MOSFET
batch was found. This batch adds eight original, condition-preserving annotations
rather than filling a numerical collection quota.

Official PDF: https://www.aosmd.com/res/data_sheets/AO3400A.pdf .
Fresh direct acquisition returned exit 0, with no access bypass or alternate-host
copy. Actual SHA-256 is
`9c60d0b6c1ddc7609a4b788a91181468d8ffe6c3e9ba425c3d8ffc5ba88c5033`;
size is 317848 bytes and page count is five. Publisher revision is **Rev 3.1,
July 2023** as printed on all five pages. No exact publication day or latest
revision guarantee is asserted from PDF creation metadata or search indexing.

Collector inspected locally rendered PDF pages 1-5; printed and PDF page numbers
agree. The table is visually necessary: flattened text renders microampere,
microsecond and ohm glyphs incorrectly. Threshold current is **250 uA**, not
250 mA; on-resistance is in **mOhm**, not mW. No precise bbox was measured.
Public access is not an open redistribution license or canonical source clearance.
No original PDF, screenshot, complete extracted text or copied plot is published.

## Bounds and deliberately unknown identity

Exact device scope is Alpha & Omega Semiconductor **AO3400A**, N-channel,
**SOT23**. This is not AO3400, AO3401A or an unnamed replacement. Page 1 supplies
G/S/D terminal labels in separate top/bottom drawings and a body-diode symbol,
but no numbered terminal table. Numerical pin mapping and full orderable/packing
identity remain **UNKNOWN**. The familiar SOT23 convention is not silently
substituted; a footprint or numbered netlist cannot be approved from this batch.

The eight annotations cover terminal/diode identity; absolute voltage stress;
threshold test semantics; four conditioned RDS(on) rows; current/power-rating
context; measured thermal conditions; diode tests; and gate-charge/capacitance
dependence. Three source-scoped warnings remain attached to every fact: numerical
identity, actual gate/load/transient inputs, and actual PCB thermal inputs.

Semantic negative cases retained in the payload:

- Threshold is not full enhancement or evidence that a controller can drive the
  intended load. There is no newly guaranteed 1.8-V, 2-V or 3.3-V drive point.
- The 125-C RDS(on) row belongs only to 10 V / 5.7 A. Typical plots do not supply
  missing high-temperature guaranteed rows at 2.5 V or 4.5 V.
- Electrical test currents and absolute ratings are not safe load-current
  recommendations. The 1.4-W/0.9-W rating uses the <=10-s thermal resistance,
  while steady-state RthetaJA is separately recorded.
- The 1-in2 FR-4/2-oz-copper measurement is not a specified user PCB copper pour,
  nor permission to ignore actual board, enclosure, ambient and pulse conditions.
- Body-diode current/recovery data do not establish inductive-load protection;
  recovery values and component capacitances remain typical.
- Qg=7 nC is a maximum only at the page-2 4.5-V/15-V/5.7-A test point. The generic
  page-5 waveform's 10-V label is not substituted for that table condition.
- No waveform, load, thermal design, GPIO drive capability, PWM frequency,
  switching loss, safe-operating-area point or avalanche capability is invented.

## Replay contract

Use a validated isolated workspace containing this pair, or the eventual
integrated repository. Each parameter lookup selects one unchanged fact and all
three complete warnings. Reader evidence stays `NOT_LOCALLY_VERIFIED` even after
recorded independent source review: lookup itself does not reopen original bytes.

```bash
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter terminal_identity_and_body_diode_orientation
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter voltage_and_junction_stress_limits
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter gate_threshold_test_not_full_enhancement
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter on_resistance_maxima_at_specified_drive
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter drain_current_and_power_rating_context
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter junction_to_ambient_board_and_time_conditions
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter body_diode_forward_and_recovery_conditions
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --parameter gate_charge_and_capacitance_test_dependencies
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake issues --source-id ao3400a-aos-r3p1-sot23
```

Fact IDs are `ao3400a-drive-01` through `ao3400a-drive-08` in the order above.
Exact identity negatives below must return `[]`, not infer substitutions:

```bash
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --manufacturer 'Other vendor'
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --device AO3400
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --device AO3401A
python3 configs/pcbknowledge_agent.py --repo WORKSPACE intake search --source-id ao3400a-aos-r3p1-sot23 --package SOT223
```

Empty results are not an electrical safety result or proof of no missing facts.
No cross-vendor/package aliases are introduced by this content slice.

## Verification and independent review

Draft JSON SHA-256 before independent review:
`05c4923fe654387b017be934ec717ea1fc5d736209de36a9c2f9d00a575e567d`.
Collector cannot self-accept. Independent source/payload review, final replay and
full isolated repository gates will be recorded below after they actually run.
Publication, successor aggregate integration and remote CI are separate later
coordinated steps; none are claimed by this draft receipt.

## Independent Agent review

Reviewer: `agent:/root/collect_mosfet_drive_constraints/review_ao3400a_constraints`.
Reviewed at `2026-10-28T04:22:38.820275+00:00`. Decision:
**AGENT_REVIEWED_UNDER_OWNER_DELEGATION**. This is not human evidence review,
owner per-fact acceptance, canonical approval, circuit qualification or permission
to redistribute the original. Collector DRAFT history is retained.

The reviewer independently recomputed the local original SHA-256 and byte size,
confirmed five pages, rendered all pages independently and visually inspected
pages 1-5. Identity, revision footers, each of eight factual annotations and all
three source warnings were checked. The official download is collector-attributed;
the reviewer did not make an independent fresh network acquisition. No factual
correction was necessary; only status, review provenance and evidence-method
metadata were updated. Numeric pin mapping remains explicitly null.

The page-2 table preserves microampere/microsecond/ohm units, exact test conditions
and min/typ/max columns. The generic page-5 gate-charge waveform does not override
the 4.5-V charge-table condition. Short-duration thermal data does not become a
steady-state rating, and no numerical load/drive/PWM qualification was inferred.

Reviewed draft JSON SHA-256:
`05c4923fe654387b017be934ec717ea1fc5d736209de36a9c2f9d00a575e567d`.
Reviewed final JSON SHA-256:
`2352020939f6f1c88dd714c31fb491672c6f5da300a76a41c5a5e1f7ec05b0ce`.

Independent replay in a separately initialized workspace: **22 payload checks**
and **13 real CLI invocations** passed with no skips. Eight parameter lookups
returned exact complete fact/source payloads and all three complete warnings;
one issues lookup returned all warnings; four exact-identity negatives returned
empty arrays. Noncanonical and reader `NOT_LOCALLY_VERIFIED` projections were
retained. Initial local harness execution used the wrong warning-response field
name (`issue`); correcting it to the executable contract's `source_issue` fixed
that harness failure without changing the payload. This receipt does not claim
the integrator's full repository gates, aggregate replay, publication or remote CI.

## Collector latest-base acceptance gates

Final JSON remains the independently reviewed SHA-256 above. The latest isolated
verification used base tree `910488c2266909ec11a3a2913507749ead489ede`, which the
integration owner verified is the published main commit
`e4c65741e80526aadbe2f3caf1ab0d56d8caa2e0` tree. The actual local base commit was
`676455de0448d61b1b08d60a754194de382acf11`; the local and public commit IDs are not
conflated. Only this new JSON/review pair was added. No shared checkout or manifest
was modified, and no external main reference was updated by the collector.

Actual commands and results on that isolated tree, 2026-10-28 UTC:

- Unchanged signal/logic replay before AO8: 165 cases, 162 facts, exit 0.
- The same pinned aggregate after AO8: expected exit 2, reporting that the batch
  set or bytes changed. This is an intentionally retained integration blocker,
  not an aggregate pass; a separately reviewed successor manifest is still needed.
- Final payload replay: 62 assertions and 13 real CLI invocations, exit 0, no
  skips. Full fact/warning payloads, identity negatives and engineering limits
  remained unchanged. All lookups retained `NOT_LOCALLY_VERIFIED`.
- `python3 configs/pcbknowledge_workflow.py config`: exit 0.
- `python3 configs/pcbknowledge_workflow.py build`: exit 0; 276 tests passed.
- `python3 configs/pcbknowledge_workflow.py test`: exit 0; 276 tests passed.
- `python3 configs/pcbknowledge_agent.py --repo . validate`: exit 0; metadata
  closure VALID, 14 noncanonical intake batches, zero canonical records.
- `python3 configs/pcbknowledge_workflow.py package`: exit 0; metadata-only
  snapshot. No original PDF, page render or complete extracted text was supplied
  to this checkout or package.
- Final English/public-distribution checks and `git diff --cached --check`: exit
  0. Package inspection found 14 batches / 170 annotations, with this reviewed
  JSON byte-identical and no originals/renders/full extracts. Review Markdown is
  a Git receipt, not a packaged file under the existing snapshot contract.

Earlier 07e8ce3-base draft/reviewed runs also passed 272-test Build and Test gates;
117 focused intake tests passed there. Those earlier runs are not substituted for
the 276-test latest-tree checks. The first collector replay harness incorrectly
targeted the raw non-Git draft directory and then used `issue` instead of
`source_issue`; both harness mistakes were fixed without changing source facts.

This pair is an immutable content handoff, not a completed successor aggregate,
remote publication, hardware qualification or remote CI receipt. The parent
integration owner retains responsibility for coherent successor pins and
exact-published-commit CI.
