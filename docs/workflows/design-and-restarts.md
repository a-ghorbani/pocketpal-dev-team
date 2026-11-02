# Going Back and Design Exploration

How a design is reworked after it is found wrong, and how competing designs are explored before the first draft. Pipeline runbook: [`pipeline.md`](pipeline.md).

## Going back: `DESIGN_INVALIDATED` and restarts

Any stage after intake replies `DESIGN_INVALIDATED` (with `INVALIDATED:`) when:

- a load-bearing `(C)` or `(F)` premise turns out false;
- a fix would contradict a recorded decision, or needs a contract, state, owner, or persisted field WHAT doesn't record (on trivial or quick work, any new contract);
- sequencing needs a decision WHAT doesn't make (planner);
- a second fix on the same premise has failed;
- most findings in a review round were introduced by the previous round's fixes;
- an operator ruling reverses part of the contract.

The architect amends WHAT (one critic pass) and names the code the amendment obsoletes. Code built on an invalidated premise is removed, not adapted.

**Restart** (new branch and worktree, fresh agents, the old PR closed with a one-line public pointer to its replacement) when:

| Observed | Restart at |
| --- | --- |
| the claim was wrong (the repro or done check isn't what the requester meant) | intake |
| an invalidated premise carries most of the design | architect |
| finding counts in one area don't fall from one review or critic round to the next | architect, for that area |
| the diff far exceeds what WHAT projected, or carries machinery with no reader | architect, or intake to slice |
| `main` moved under the design: a sibling landed that breaks an assumption | architect, on the new `main` |
| the PR sat for weeks far behind `main` with no review | intake, to re-slice |

A restart keeps `evidence.md` and its receipts, spike receipts, behaviour tests, `decisions.md` (the reversed row marked), and review findings as scenarios the new design must handle; it discards the implementation of the invalidated part. Not restart triggers: a local bug in a sound design, one finding however severe, taste tweaks that leave the contract alone, "it's almost done".

## Design exploration

`DESIGN_EXPLORATION=YES`: required for complex tasks; optional for standard ones with competing architecture shapes, persistence or migration risk, native or model-execution changes, or trust-boundary changes.

Before the architect's first draft, the orchestrator writes the handoff block to `<STORY_DIR>/handoff.txt` and runs the **design arena** in the background: `tools/design-arena.sh run <STORY_DIR>`.

- Each runner in `config/design-arena.conf` (models from different providers) designs independently in its own tmux lane, writing `<STORY_DIR>/candidates/<name>/what.md` and spikes.
- A judge from a provider other than the architect's scores the candidates and recommends a base (`candidates/judge.md`). The shipped conf assumes a Claude orchestrator; under another harness, set the judge to a different provider.
- The architect then runs in merge mode. On exit 1 (fewer than two candidates) or exit 2 (environment or usage error, reported in the reply) it explores alone; on exit 3 (no judge) it merges without one.

The critic reviews only the merged `what.md`. `tools/design-arena.sh status|cleanup <STORY_DIR>` inspects or clears a run.
