# Implementer brief (standing)

This is the standing task for an implementing agent in continuous mode. It does
not change per round; the work queue is `TODO.md`. Edit this file only when the
operating procedure changes.

Copy everything below the line into the implementing agent's task.

---

You are continuing PcbKnowledge in **continuous mode**. G1 is at A2. The goal is
that a simple design brief becomes a manufacturable board; this repository
supplies the knowledge, expansion, handoff files and checks, and never places or
routes a board.

## Read first

1. `AGENTS.md` (all of it; sections 3, 7 and 10 matter most)
2. `TODO.md`: owner decisions, the latest stage receipt and review, and the open
   stages
3. `docs/review-checklist.md`
4. ADR-022, ADR-023, ADR-024 and any newer ADR

## How to work

- Take the first unchecked item of the lowest open stage in `TODO.md` and keep
  going through the stages. Skip `(owner-only)` items. Stop only at an
  `(escalate)` condition listed in `TODO.md`, or a gate failure you cannot fix.
- Make decisions yourself: use the D-number defaults; when you need a new one,
  choose a sensible default, add the next D-number with a one-line reason, and
  continue. Substitute parts whose sources are inaccessible (D10).
- Keep each change the smallest that serves the stage. Delete what becomes unused.
- Data commits (`[data]`) and code or contract commits stay separate.

## At every stage exit

1. Run the full gate (AGENTS section 10).
2. Start an independent reviewer agent with `docs/review-checklist.md`. Fix its
   findings in this stage; put anything unfixable in `TODO.md`.
3. Record a receipt of one to three lines in `TODO.md` (commits, test count,
   coverage or acceptance result, review summary) and advance the status line.
4. `git fetch`, rebase onto `origin/main` if it moved, rerun affected tests, push.
   Never force-push. Wait for CI and fix failures in the same stage.
5. Continue with the next stage in the same session.

## Report when you stop

- Stages completed with commit hashes and test counts.
- Acceptance and coverage per brief (`v2 coverage --all` once it exists).
- New D-numbers and substitutions.
- Review findings and how each was resolved.
- Why you stopped, and what the next item is.
