# Review Loop and Finalization

The independent review rounds after the gates pass, and closing a task once its PR is merged. Pipeline runbook: [`pipeline.md`](pipeline.md).

## Independent review loop

`review-pr <PR>` runs only once `tools/pr-gates.sh <PR>` passes. Output: `workflows/reviews/PR-<n>/round-<N>/final.md`. Every round counts toward the cap of 2, whatever the previous verdict; a third round needs an operator or PM ruling, logged in `decisions.md`.

- `APPROVE` with only SUGGESTIONs ends the review; suggestions are listed as follow-ups in the published review and trigger no round.
- `REQUEST_CHANGES`, in order:
  1. Intake sets up the PR-fix story `PR-<n>-fix` (first round only: it carries `evidence.md` and `decisions.md` over and points `INTENT_BRIEF`, `WHAT`, `HOW` at the original story).
  2. The orchestrator writes the **fix brief** `<STORY_DIR>/review-feedback-round-<N>.md` from `templates/review-feedback-template.md` and logs the round's review dismissals in `decisions.md`. A finding that contradicts `decisions.md` or WHAT, that a previous round already fixed once, or whose fix needs a contract, state, owner, or persisted field WHAT doesn't record (on trivial or quick work, any new contract) goes to the architect as `DESIGN_INVALIDATED`, not into the brief.
  3. `pocketpal-plan-critic` reviews the brief (fix-brief mode, paths only) before any code.
  4. implementer → tester (re-running the brief's evidence rows and the surfaces each fix touched) → pipeline-reviewer → gates → review.

## Finalization after the human merges

Once the PR is merged, the `/start-task` session finishes without asking again:

- replace the PR's `(pending #<n>)` markers in `context/architecture/` with current-truth wording (path-scoped commit);
- distill the task's lessons (`AGENTS.md`, Lessons: false premises, real findings a stage should have caught, tool and device traps, general rulings);
- close the tracker item (`context/issue-tracking.md`), add a closing note to the story, and tell sessions whose PRs depend on the change;
- remove the task's worktrees (`<TASK-ID>`, `PR-<n>`, `PR-<n>-e2e`) with `./tools/remove-worktree.sh <name> --yes`, checking each is clean first; stop and report one with uncommitted or unpushed work.
