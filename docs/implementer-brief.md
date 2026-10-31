# Implementer brief (standing)

This is the standing task for an implementing agent in continuous mode. It does
not change per round; the work queue is `TODO.md`. Edit this file only when the
operating procedure changes.

Copy everything below the line into the implementing agent's task.

---

You are continuing PcbKnowledge in **continuous mode**. The goal is that a
simple design brief becomes a manufacturable board. This repository is the knowledge
base serving PcbAtlas: it supplies the knowledge, expansion, handoff files and
constraint checks, and PcbAtlas owns placement, routing, DRC and fabrication output
(D78). The current acceptance level of each golden design is in `TODO.md`.

## Read first

1. `AGENTS.md` (all of it; sections 3, 7 and 10 matter most)
2. `TODO.md`: owner decisions, the latest stage receipt and review, and the open
   stages
3. `docs/review-checklist.md`
4. ADR-022 to ADR-025 and any newer ADR

## How to work

- Take the first unchecked item of the lowest open stage in `TODO.md` and keep
  going through the stages. Skip `(owner-only)` items. If a stage blocks, record
  the blocker, park it and start the next stage. Stop only when every remaining
  stage is parked, at an `(escalate)` condition, or at a gate failure you cannot
  fix.
- Two developers work on `main` at once (D77). `TODO.md` is the only coordination channel.
  Ethan works only `(ethan)` items and Wisdom skips them. Rebase before every push, do
  not revert each other's work, and end each commit body with `Developer: Wisdom` or
  `Developer: Ethan`. Run one implementing session per developer. Sub-agents for
  review and synthesis are expected.
- **Commit and push; do not stop at commit.** You are not on the owner's computer,
  and only `origin/main` reaches the owner. This brief is standing authorization to
  commit and push to `main`. After each coherent commit group: run the affected tests,
  `git fetch`, rebase onto `origin/main` if it moved, push, and check CI. Never
  force-push, and never leave local-only commits for someone else to import. Do not add
  "original local commit" trailers.
- A red CI job on `main` on any operating system goes ahead of the queue. Do not
  assume Linux results hold on macOS or Windows.
- `build/` stays on your machine. A result counts only when a CLI command regenerates
  it from a clean checkout; hand-driven Python call chains do not count.
- `NOT_CHECKABLE` is not a pass.
- This repository is not an algorithm library (D78). You may use KiCad and Freerouting
  as external test tools to find knowledge errors. Fix each finding in the catalog with
  a tool-free test; do not add placement, routing, DRC or fabrication algorithms.
- Sources: follow D38. A public manufacturer datasheet is usable whatever the
  website terms say; download one at a time and never work around bot checks.
  When an essential parameter is `UNKNOWN` in one part, select a part whose
  datasheet states it rather than carrying the `UNKNOWN` into a design.
- Make decisions yourself: use the D-number defaults; when you need a new one,
  choose a sensible default, add the next D-number with a one-line reason, and
  continue. Substitute parts whose sources are inaccessible (D10).
- Keep each change the smallest that serves the stage. Delete what becomes unused.
- Data commits (`[data]`) and code or contract commits stay separate.

## When something blocks you

Do not stop while any item of yours remains. Try the listed action, record the blocker in at
most three lines, and move to your next item.

| Situation | Action |
|---|---|
| Design input, budget, test condition or protocol is missing | It is a decision. Choose a sensible `ENGINEERING_DEFAULT`, add a D-number with one line of reason, continue |
| `evidence fetch` fails in your sandbox (DNS, mount, HTTP 403) | Try once. Then download manually and use `evidence add`. If that fails, keep the record `DRAFT`, add the source to the Owner evidence list in `TODO.md`, and continue with other work. Do not claim byte verification |
| Source is unavailable or a part lacks an essential parameter | Substitute an equivalent part under D10 and record it |
| Source wording is ambiguous | Read the cited page. Choose the most conservative physically achievable reading that keeps the number, and record it. If that changes how an existing check measures, add an owner question and move on |
| Constraint looks physically impossible | Prove it with a lower-bound test, add an owner question with a proposal, keep the rule, and move on |
| Checker cannot prove some geometry | Return `NOT_CHECKABLE` with a typed reason, list it in `TODO.md`, and move on |
| External tool is missing | Result is `NOT_RUN`. Continue, and list it in `TODO.md` if the owner should run it |
| Test failure from the other developer's push | If it blocks you, make the smallest fix, state it in the commit body, and continue. Do not revert their work |
| Rebase conflict | Keep both sides. In `TODO.md`, keep both developers' lines |
| Review finding is outside your item | Add it to `TODO.md` as an item and continue |
| Two different attempts at one item have failed | Record what you tried, park that item, and go to the next |

Decide without asking whenever a D-number default or this table covers the case. An owner question
never stops the session. Only the escalation list in `TODO.md` limits what you may do: for those
cases never take the weakened path, and keep working on everything else. Stop only when all of your
items and every claimable cycle are done or parked.

## Pace

Finish an item at its stated tests, then move on. Do not gold-plate one checker while later items wait.
One independent review pass per item group is enough unless it finds a real defect.

## At every stage exit

1. Run the full gate (AGENTS section 10).
2. Start an independent reviewer agent with `docs/review-checklist.md`. Fix its
   findings in this stage; put anything unfixable in `TODO.md`.
3. Record a receipt of one to three lines in `TODO.md` (commits, test count,
   coverage or acceptance result, review summary) and advance the status line.
4. `git fetch`, rebase onto `origin/main` if it moved, rerun affected tests, push.
   Never force-push. Wait for every CI job and fix failures in the same stage.
5. Continue with the next stage in the same session.

## Before you end any session

Interrupted or parked work included:

1. Commit finished work and push it. Update `TODO.md` so unfinished work is findable.
2. Confirm `git status` is clean and `git rev-parse HEAD` equals
   `git rev-parse origin/main`.
3. Confirm CI for that commit, or report the exact jobs still running or failed.

## Report when you stop

- The pushed `HEAD` hash and the CI result of each job.
- Stages completed with commit hashes and test counts.
- Acceptance and coverage per brief (`v2 coverage --all` once it exists).
- New D-numbers and substitutions.
- Review findings and how each was resolved.
- Why you stopped, and what the next item is.
