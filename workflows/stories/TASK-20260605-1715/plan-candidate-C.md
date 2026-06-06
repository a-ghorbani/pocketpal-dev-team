# Plan Candidate C: docs-first contract-lock then implement

## Metadata
- **Task ID**: TASK-20260605-1715
- **Candidate**: C
- **Design source**: `./workflows/stories/TASK-20260605-1715/what.md`

## Strategy
Repair the architecture-doc drift FIRST (rewrite chat-flow.md Invariants/§4/§5/§9f
and pals-and-talents.md §5a I8 from aspirational `(C)` to match the WHAT's real
fields), locking the implementation contract in the canonical docs, then implement
bottom-up against the corrected docs. Inverts the usual "docs absorb in same PR as
final step" ordering.

## Step Shape
1. Docs drift repair (both flow docs) up front.
2..N. Same data-up implementation as candidate A.

## Commit Boundaries
- Docs commit first, then per-layer.

## Verification
- Same as A; plus the docs commit is reviewed before code so reviewers gate the
  contract early.

## Risks
- The implementer commonly discovers a name/shape nuance during coding (e.g. exact
  store-clear call sites, snackbar host wiring) — docs written first will need a
  second corrective edit, producing doc churn and a stale-doc window mid-PR.
- AGENTS.md mandates docs land in the SAME PR, not necessarily first; first-ness
  buys little here since this is single-PR.

## Rejected If
- Front-loading docs creates a stale window if implementation reveals a nuance —
  better to absorb docs as the final step (A) once the code shape is concretely
  known. Rejected for that reason.
