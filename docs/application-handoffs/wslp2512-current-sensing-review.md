# Independent review: WSLP2512 current-sensing input card

- Task: [issue #33](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/33).
- Author/publisher: Agent `/root/document_shunt_application_inputs`.
- Distinct reviewer: Agent `/root/document_shunt_application_inputs/review_shunt_card`.
- Review completed: 2026-10-28T23:19:57.581069+00:00.
- Decision: **PASS for the bounded documentation handoff**, not circuit approval.
- Reviewed [card](wslp2512-current-sensing.md) SHA-256:
  `7078d7a494ccf8bfbd6d2ce56070218250bbdf37bedac610a18507933221b651`.
- Clean pinned technical checkout: `5cb96b866a941ad0ad905e6ce7f0d130477f5852`.
- Separately replayed clean current base: `77440b29cb74ad2f55849ab3cddb830321e3396f`.
- Source JSON SHA-256, identical at both snapshots:
  `91abaf2e01f2cbd092e2e4e33f194a59bacf1eebcb33aeb07ff28b1ef775414b`.

## Checks actually performed

Read the complete card, accepted source JSON and historical source review.
Compared all six full `wslp2512-sense-01` through `06` fact objects, including
values, conditions, provenance and source metadata, against source-filtered
retrieval. Compared all three complete source-issue objects and attached warning
lists structurally, normalizing only list order by ID. The full warning text,
status and historical provenance are preserved in the card.

Executed the five literal card commands independently in both clean detached
checkouts. All ten required executions exited 0 and all full stdout hashes
matched. Command SHA-256 uses literal UTF-8 bytes without a trailing newline;
stdout SHA-256 includes its final newline. These are retrieval checks, not an
engineering evaluation of the invented scenario.

| Recipe | Literal command SHA-256 | Full stdout SHA-256 |
|---|---|---|
| Source search | `8ca71e9e75a613de38b9a0594d9520d29f0e767404abed3eacffb35ca212e0be` | `008415d04d843b68da0bc20f00cf3e50bc85d5cc4c7b97954c24adcfacf4b099` |
| Source issues | `bb13825cf2fd3c8cbdd00afd84b1e1f2817072e1de4a6fad1700884ee5eba84c` | `6de24d2b3c8684806c20a78c5055479804e0c4bd6433f45fb77c9ec436ca72aa` |
| Wrong device | `98f0ab05156bfe8a645119b19ec40885bcf2102d692bda176f40cd958e3a0f78` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong package | `f861503a21a5de04ca5dc0a4a464bdfe2b8ad57c240f7d53429de466938fe106` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong revision | `b2121d918c224e5a7ee0b88d529ee0c3bb5f073137d8fd6c6114663797f250f6` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

The three selected warnings are `wslp2512-thermal-inputs-unknown`,
`wslp2512-measurement-inputs-unknown` and
`wslp2512-pulse-envelope-not-established`. Wrong R0200 orderable, package 1206
and revision 09-Sep-2023 independently fail the exact structured identity of
this scoped source. Each returned an empty array, not a conclusion about safety,
compatibility, existence or global evidence availability.

## Content disposition and limits

No correction was required. The single invented 10-A DC, 50-C ambient, desired
1%-system-accuracy case remains distinct from actual board inputs. Independent
nominal arithmetic confirms 10 * 0.01 = 0.1 V and 10 squared * 0.01 = 1 W;
neither value is an operating bound or proof of thermal suitability.

The card retains component TCR including terminals (75 ppm/C, -55 to 155 C,
0.007 to 0.5 ohm row), rather than substituting the alloy-only less-than-20 value.
The exact 0.007-to-0.01-ohm terminal row, T and selected pad dimensions remain
conditioned metadata, not a complete footprint or Kelvin-error guarantee.
Load-life conditions and the additive 0.0005-ohm term are retained without
inventing applied power or translating the test into service accuracy. P70,
ambient derating and working-voltage arithmetic do not establish safe board
current/power. The illustrative pulse graph is not digitized or qualified.

The complete missing current/thermal/layout/analog-chain/calibration inputs and
needed error-budget analysis remain explicit. No amplifier, footprint, Kelvin
connection, pulse envelope or circuit is selected or certified. Consumer
`canonical: false`, `human_reviewed: false` and `NOT_LOCALLY_VERIFIED` semantics
were checked. No original PDF/HTML retrieval, byte/visual audit, human review,
canonical approval or electrical qualification was performed. The historical
source review is not claimed as new work. Publisher separately owns all full
gates, current-main reconciliation, exact remote tree and terminal CI; this
content review does not claim those checks.
