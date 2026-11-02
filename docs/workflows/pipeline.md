# Delivery Pipeline Playbook

Runbook for the orchestrator: the top-level `/start-task` session and the PR-fix loop it drives. Invariants every agent obeys are in `AGENTS.md`.

## Dispatching a role

Run each role as a subagent with the handoff block as its prompt:

| Harness | Dispatch |
| --- | --- |
| Claude Code | `Agent` tool, `subagent_type: pocketpal-<role>` |
| Codex | `spawn_agent` with agent `pocketpal-<role>` |
| opencode | `task` tool with `pocketpal-<role>` (or `@pocketpal-<role>`) |
| pi | `subagent` tool: `agent: pocketpal-<role>`, `agentScope: "project"`, `confirmProjectAgents: false` |
| no subagent support | start a fresh session, have it read `agents/pocketpal-<role>.md`, and give it the handoff block |

Roles are leaves: only the orchestrator dispatches.

## Handoff block

Intake creates it; every stage ends its reply with it, updating `VERDICT` and any key it learned. Pass the returning stage's whole reply (report plus block) verbatim to the next role. Critics get the block alone (paths only, never the producer's reasoning) and may rerun any spike receipt. Omit keys that don't apply.

```text
VERDICT: <the stage's verdict — see Routing>
TASK_ID: TASK-YYYYMMDD-HHMM | PR-<n>-fix
WORKTREE: ./worktrees/TASK-YYYYMMDD-HHMM | ./worktrees/PR-<n>
BRANCH: feature/TASK-YYYYMMDD-HHMM | pr-<n>
STORY_DIR: ./workflows/stories/<TASK_ID>
COMPLEXITY: trivial | quick | standard | complex
PLAN: YES | NO                                 # planner runs (see Shape)
NATIVE_CHANGES: YES | NO
DESIGN_EXPLORATION: YES | NO
INTENT_BRIEF: <STORY_DIR>/intent-brief.md
EVIDENCE: <STORY_DIR>/evidence.md
DECISIONS: <STORY_DIR>/decisions.md
WHAT: <STORY_DIR>/what.md                      # standard / complex
HOW: <STORY_DIR>/how.md                        # PLAN=YES only
FIX_BRIEF: <STORY_DIR>/review-feedback-round-<N>.md   # PR-fix rounds
ARCHITECTURE_DOCS: ./context/architecture/<flow>.md, ...
FIGMA_FILE: <file key>                         # Figma-pinned slices
NODE_IDS: <node id>, ...                       # Figma-pinned slices
VISUAL_CAPTURE_PATHS: <png> <png> ...          # tester, when captures exist
PR: #<n>                                       # pipeline-reviewer, once the draft PR exists
INVALIDATED: <decision or premise id>: <one line>     # with DESIGN_INVALIDATED
```

Take `WORKTREE`, `BRANCH` and `STORY_DIR` from the block; never rebuild them from `TASK_ID`. Intake's prompt is self-contained: full request text, acceptance criteria, constraints, known baseline/version context; answers to its `NEEDS_INPUT` go in a new invocation.

## Shape

| Level | When | Stages |
| --- | --- | --- |
| **trivial** | Single-file copy / config / typo / version bump. < 20 lines. No new contract. | intake → implementer → tester → pipeline-reviewer |
| **quick** | 1–3 files; a bug fix or small enhancement inside an existing flow doc's contracts. | as trivial |
| **standard** | Touches a contract (data model, single-writer, rendering, persistence, wire format, trust boundary). | intake → architect ⇄ critic → implementer (slice → slice review → finish) → tester → pipeline-reviewer |
| **complex** | Cross-flow, new flow, architecture-changing. | standard, with `DESIGN_EXPLORATION=YES` |

Intake classifies by the **riskiest contract touched**, not size. Security, schema, and breaking-API changes are at least standard, and so is a task whose flow doc visibly contradicts the code.

**Planner (`PLAN=YES`, set by intake or the architect)** runs after the architect-critic only when sequencing is itself a risk: several PRs, a data migration, a native build change that must land in steps, or a feature-flag rollout. Otherwise the implementer sequences its own work.

**Slicing.** When the projected diff exceeds ~1,500 lines or WHAT can't fit its length budget, the architect proposes slices and replies `NEEDS_INPUT`; each slice becomes its own task.

## Routing

Dispatch the next role from the returning stage's verdict at once, with no interactive prompt or approval gate:

| Stage | Verdict | Next |
| --- | --- | --- |
| intake | `NEEDS_INPUT` | stop; surface the questions |
| intake | `READY`, trivial / quick | implementer |
| intake | `READY`, standard / complex | architect |
| intake | `READY`, PR fix | orchestrator writes the fix brief → plan-critic (fix-brief mode) |
| architect | `DRAFTED` | architect-critic |
| architect-critic | `LGTM` | planner when `PLAN=YES`, else implementer |
| architect-critic | `HAS_CONCERNS` / `HAS_BLOCKERS` | architect (revision; max 2 rounds) |
| planner | `DRAFTED` | plan-critic |
| plan-critic | `LGTM` | implementer |
| plan-critic | `HAS_CONCERNS` / `HAS_BLOCKERS` | the producer revises: planner for HOW, the orchestrator for a fix brief (max 2 rounds) |
| implementer | `SLICE_READY` | architect-reviewer, slice mode (see Tracer slice) |
| architect-reviewer (slice) | `LGTM` / `HAS_FINDINGS` | implementer, to finish (addressing findings first) |
| implementer | `COMPLETE` | tester |
| tester | `COMPLETE` | pipeline-reviewer (redesign slices: design-parity-reviewer first) |
| tester | `IMPLEMENTATION_BUG` | implementer |
| design-parity-reviewer | `APPROVED` / `NEEDS_FIXES` | pipeline-reviewer / implementer (max 2 rounds) |
| pipeline-reviewer | `APPROVED` (with `PR`) | tester in post-PR mode when `evidence.md` has CI-APK rows; then the gates |
| `tools/pr-gates.sh` | `ci` or `evidence` FAIL | implementer (CI) or tester (evidence); max 2, then `BLOCKED` |
| `tools/pr-gates.sh` | all PASS | independent review (`review-pr`) |
| review-pr | `NOT_READY` | as a gate FAIL above; no round consumed |
| pipeline-reviewer | `REQUEST_CHANGES` | implementer |
| pipeline-reviewer | `ESCALATE` (branch already on `origin/main`) | stop; the merge gate was bypassed |
| any stage after intake | `DESIGN_INVALIDATED` | architect (amendment). Trivial / quick: the orchestrator re-classifies to standard and dispatches the architect in the same worktree |
| any stage | `NEEDS_INPUT` / `ESCALATE` / `BLOCKED` | stop |

## Autonomous-run contract

Stop only for:

- `NEEDS_INPUT` (each question carries a recommended answer), `ESCALATE`, or `BLOCKED` (environment or tooling; design conflicts are `DESIGN_INVALIDATED`) from any stage
- `HAS_BLOCKERS` persisting after round 2 of a critic loop
- incomplete required independent review artifacts
- failed mandatory verification
- `BLOCKER` or `CONCERN` findings persisting after review round 2

When a PM session runs the queue, these stops go to the PM first (`skills/pm`).

## Evidence plan

`evidence.md` (`templates/evidence-template.md`) lists what the change must show to count as done:

1. **The claim.** A bug: the reporter's symptom reproduced on `main` (red) before the fix, then the same steps on the branch (green). A feature: the done check in the requester's words, one that can fail.
2. **Where** it must hold: platforms; real system vs fake.
3. Every risk row below that matches what the request touches.

| The change touches | It always needs |
| --- | --- |
| a surface an existing e2e spec drives (grep `e2e/specs` for the changed screens, stores, services) | those specs, on the PR's CI APK (`/run-pr-e2e`) |
| a llama.rn bump, backend selection, inference code | `bench` smoke and focused, compared with the baseline and the previous llama.rn PR; `memory-profile`; a device run with a stateful (hybrid / recurrent) and a multimodal model as well as a transformer |
| model loading | `bench` smoke and `memory-profile` |
| native dependencies, Gradle, Podfile, podspecs, ProGuard / dependency trims | iOS and Android release builds; `bench` smoke; a real-store `.e2e` smoke build plus a negative control |
| purchases, store, entitlements, Plus | `iap-plus` and a real store sandbox run, not only FakeStore |
| remote-server wire format | a strict OpenAI-compatible server as well as llama-server; read what the server applied (`/slots`), not the status code |
| downloads, network resilience | the slow-network proxy (stall, resume, terminal failure) and a permission decline |
| sheets, keyboard, layout | iOS and Android, rotation, multi-window or tablet width (`wm density`), dark mode, from a focused input |
| a heuristic that filters, blocks, or parses | false-positive cases that must still pass, alongside the hostile ones |
| imported or external data reaching a file, network, or render sink | a hostile input at each sink that is reachable on `main` |
| voice, audio, mic, TTS / ASR engines | the voice specs and `tts-memory-profile`; a device run covering first-time setup, interruption, and a model that does not fit |
| iOS-only code paths | a run through `ios-router`; this host has no iOS |
| render-heavy paths, perf claims | the Reassure gate; an on-device A/B for any claimed speed-up |

| Stage | Evidence work |
| --- | --- |
| intake | writes the claim, the platforms, the matching rows |
| architect | adds an item per canonical scenario and per required WHAT section it fills |
| implementer, fix rounds | add items for touched surfaces the plan didn't foresee |
| tester | runs each item as a command, spec, or device run and records the receipt. **CI APK** rows (e2e specs, bench, memory profiles, store runs) run post-PR on the draft PR's CI APK; compare any red against `main` before calling it |
| pipeline-reviewer | checks every pre-PR item has a receipt or a documented reason it could not run; posts the **evidence comment** (what was proven and its receipt, public references only, captures inline); the tester appends post-PR rows. `tools/pr-gates.sh` fails without it |

Any stage may add an item; dropping one needs a reason in its row. A capture is an evidence item whose receipt is an image.

## Decisions and product calls

`decisions.md` logs every decision except the architect's engineering ones (WHAT §8); later stages and reviewers read it.

| Kind | Who decides | Rule |
| --- | --- | --- |
| **Fact** (library behaviour, platform limit, what a server accepts) | nobody: it is proven | `(C)` read from code at `file:line`, or `(F)` proven by a spike with its receipt |
| **Product call** (user-visible behaviour the request leaves open, copy, accepting a limitation or regression) | the operator | logged with a recommended default; one that shapes the contract is `NEEDS_INPUT`, the rest proceed on the default and are listed in the stage reply |
| **Engineering choice** | the architect | a WHAT (D) row, defended against a real alternative |
| **Operator or PM ruling** | as given | logged verbatim with its date |
| **Review dismissal** | the review's refutation | logged from `final.md` by the orchestrator, its only writer; later rounds don't re-raise it without new evidence |

A decision is reversed only by a new row that names the one it replaces.

## Tracer slice

Standard and complex work: the implementer first commits the thinnest end-to-end slice of the WHAT's core path; `pocketpal-architect-reviewer` reviews the slice diff against the WHAT. A finding that contradicts a WHAT decision or premise comes back as `DESIGN_INVALIDATED`.

## Going back: `DESIGN_INVALIDATED` and restarts

Any stage after intake replies `DESIGN_INVALIDATED` (with `INVALIDATED:`) when:

- a load-bearing `(C)` or `(F)` premise turns out false;
- a fix would contradict a recorded decision;
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

## Independent review loop

`review-pr <PR>` runs only once `tools/pr-gates.sh <PR>` passes. Output: `workflows/reviews/PR-<n>/round-<N>/final.md`. Every round counts toward the cap of 2, whatever the previous verdict; a third round needs an operator or PM ruling, logged in `decisions.md`.

- `APPROVE` with only SUGGESTIONs ends the review. Suggestions go to the PR body's follow-ups; none triggers a round.
- `REQUEST_CHANGES`, in order:
  1. Intake sets up the PR-fix story `PR-<n>-fix` (first round only: it carries `evidence.md` and `decisions.md` over and points `INTENT_BRIEF`, `WHAT`, `HOW` at the original story).
  2. The orchestrator writes the **fix brief** `<STORY_DIR>/review-feedback-round-<N>.md` from `templates/review-feedback-template.md` and logs the round's review dismissals in `decisions.md`. A finding that contradicts `decisions.md` or WHAT, or that a previous round already fixed once, goes to the architect as `DESIGN_INVALIDATED` instead of into the brief.
  3. `pocketpal-plan-critic` reviews the brief (fix-brief mode, paths only) before any code.
  4. implementer → tester (re-running the brief's evidence rows and the surfaces each fix touched) → pipeline-reviewer → gates → review.

## Finalization after the human merges

Once the PR is merged, the `/start-task` session finishes the task without asking again: replace `(pending #<n>)` markers for the PR in `context/architecture/` with current-truth wording (path-scoped commit), add a closing note to the story, tell sessions whose PRs depend on the change, and remove the task's worktrees (`<TASK-ID>`, `PR-<n>`, `PR-<n>-e2e`) with `./tools/remove-worktree.sh <name> --yes`. Check each worktree is clean first; stop and report one that has uncommitted or unpushed work.

## Design exploration

`DESIGN_EXPLORATION=YES`: required for complex tasks; optional for standard ones with competing architecture shapes, persistence or migration risk, native or model-execution changes, or trust-boundary changes. The architect explores; the critic reviews only the synthesized `what.md`.

## Redesign slices (Figma-pinned work)

For a task that implements a Figma node id, the implementer follows the `figma-implement` skill and the design-parity-reviewer runs as routed above (`docs/workflows/visual-capture.md`, Flavour C).
