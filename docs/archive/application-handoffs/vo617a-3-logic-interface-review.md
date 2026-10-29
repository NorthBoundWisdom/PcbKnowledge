# Independent review: VO617A-3 application-input card

- Task: [issue #32](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/32).
- Author/publisher: Agent `/root/document_optocoupler_application_inputs`.
- Distinct reviewer: Agent `/root/document_optocoupler_application_inputs/review_optocoupler_card`.
- Review completed: 2026-10-28T22:21:23Z.
- Decision: **PASS for this bounded documentation handoff**, not circuit approval.
- Reviewed [card](vo617a-3-logic-interface.md) SHA-256:
  `0fd5f58057d0d77f4cb3ac2c6bb80e540452a4900247ffb49f8907d6e22d533b`.
- Pinned technical checkout: `f97bb140134de4463284287bb13b6aa6b58eb7c3`.
- Separately checked current base: `e442b8e1ab9144f1c1c19b6b6b4b74c70b00ae61`.
- Source JSON SHA-256 (identical at both snapshots):
  `adc2ce86339add3ad91ee96225abdc2bc4343dd6e994afc0e4e50f35ae60e64c`.

## Independent checks actually performed

Read the complete card, accepted source JSON and adjacent historical source
review. Compared all eight `vo617a-3-logic-01` through `08` complete fact objects,
source objects, conditions, provenance and every attached warning structurally,
normalizing only warning-list order by ID. Independently compared the three
complete issue objects and their source/provenance, and verified all three full
warning descriptions and unresolved statuses appear verbatim in the card.

Executed each of the five literal commands in the card on the clean detached
pinned checkout and separately on the current base. All ten commands exited 0;
all complete stdout hashes matched the card. Command hashes below are SHA-256
of each literal command's UTF-8 bytes without a trailing newline. Stdout hashes
include the final newline. These are retrieval checks, not circuit evaluation.

| Card recipe | Literal command SHA-256 | Full stdout SHA-256 |
|---|---|---|
| Source search | `985056d30ab04ce3309c44dd3eff9268a3c0e872fd56efde52b27d299ba60677` | `643177c2c5998cdcd3a78e5c4b108802705d1f4db1e4cd10010f81d6d9e929ec` |
| Source issues | `d45cdf938c900c6dec6fb52baa7aeda874f0dc6652987e6b6c2a67b4faef92d1` | `cd2e432bedfa68831c9c77402fd43bc7e192218ba7fabea5ce7c5a077214b7ac` |
| Wrong bin VO617A-2 | `e639cb61be7abe10726dde8f155f212b1a309c47c9d8ace0b2e50fcb7ce0d468` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong package SMD-4 | `30b46d21a98b67e76d7fd3bea2e5511d43107f60719b89df43df48facb107584` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong revision Rev. 2.7 | `dc38e6de0297bbd66e097f3fb7e7419cb1881c1f1655b323926542993d4ee8cf` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

Expected positive selections are the eight exact fact IDs and the three warnings
`vo617a-3-saturated-test-current-conflict`, `vo617a-3-logic-margin-unknown` and
`vo617a-3-isolation-option-not-qualified`. The negatives are independently
justified by exact source identity VO617A-3, standard DIP-4, Rev. 2.8: each wrong
structured value excludes every scoped fact. Empty output is not a compatibility,
safety or global evidence-absence conclusion.

## Content disposition and limits

No correction was required. The blank card and exactly one synthetic case keep
5-mA LED drive, 3.3-V rail, 1-kohm pull-up and desired 10-kbit/s rate as invented
nominals only. Missing actual receiver/thresholds, tolerances, waveforms, thermal
and lifetime evidence remain unknown. The card separates active-region CTR,
1-mA-collector saturation testing, 60-mA forward-voltage testing, conditioned
leakage and typical non-saturated timing. It preserves the 5-mA table versus
10-mA Figure 3 conflict without selecting a setup or deriving qualified delay.
No resistor, replacement, signaling rate, logic margin or isolation system is
approved; matching one nominal load does not establish test equivalence.

Consumer `canonical: false`, `human_reviewed: false` and
`NOT_LOCALLY_VERIFIED` semantics were checked. This review reused accepted
metadata only: no original PDF retrieval, byte audit, visual inspection, human
review, canonical licensing clearance or electrical/safety qualification was
performed. No originals, extracts or images are included. Publisher separately
owns full gates, latest-main reconciliation, exact remote tree and terminal CI;
this content review does not claim those checks. Their receipt belongs in #32.
