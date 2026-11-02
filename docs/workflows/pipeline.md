# Delivery Pipeline Playbook

Runbook for the orchestrator: the top-level `/start-task` session and its PR-fix loop. Invariants every agent obeys: `AGENTS.md`.

## Dispatching a role

Run each role as a subagent with the handoff block as its prompt:

| Harness | Dispatch |
| --- | --- |
| Claude Code | `Agent` tool, `subagent_type: pocketpal-<role>` |
| Codex | `spawn_agent` with agent `pocketpal-<role>` |
| opencode | `task` tool with `pocketpal-<role>` (or `@pocketpal-<role>`) |
| pi | `subagent` tool: `agent: pocketpal-<role>`, `agentScope: "project"`, `confirmProjectAgents: false` |
| no subagent support | a fresh session that reads `agents/pocketpal-<role>.md`, given the handoff block |

Roles are leaves: only the orchestrator dispatches.

**Devices and iOS.** Stage roles never call agistry. Before a stage that drives a phone (tester device rows, an architect device spike), the orchestrator claims one (`agistry.sh claim`), passes it as `DEVICE`, and releases it with a note when the stage returns. A stage marks rows that need iOS `needs ios-router` with the exact check; the orchestrator requests a worker from `ios-lab:router` (`skills/ios-router`), relays the check, and records the worker's receipts in those rows before routing on.

## Handoff block

Intake creates it; every stage ends its reply with it, updating `VERDICT` and any key it learned. Pass the returning stage's whole reply (report and block) verbatim to the next role. Critics get the block alone (paths only, never the producer's reasoning) and may rerun any spike receipt. Omit keys that don't apply.

```text
VERDICT: <the stage's verdict — see Routing>
TASK_ID: TASK-YYYYMMDD-HHMM | PR-<n>-fix
WORKTREE: ./worktrees/TASK-YYYYMMDD-HHMM | ./worktrees/PR-<n>
BRANCH: feature/TASK-YYYYMMDD-HHMM | pr-<n>
STORY_DIR: ./workflows/stories/<TASK_ID>
COMPLEXITY: trivial | quick | standard | complex  # for a bug, set by the repro
CLAIM: bug | feature
PLAN: YES | NO  # planner runs (see Shape)
NATIVE_CHANGES: YES | NO
DESIGN_EXPLORATION: YES | NO
NEEDS_RESEARCH: YES | NO
INTENT_BRIEF: <STORY_DIR>/intent-brief.md
CONTEXT: <STORY_DIR>/context.md  # lessons and past work that apply (intake)
RESEARCH: <STORY_DIR>/research.md  # when the researcher ran
EVIDENCE: <STORY_DIR>/evidence.md
DECISIONS: <STORY_DIR>/decisions.md
WHAT: <STORY_DIR>/what.md  # standard / complex
HOW: <STORY_DIR>/how.md  # PLAN=YES only
FIX_BRIEF: <STORY_DIR>/review-feedback-round-<N>.md  # PR-fix rounds
ARCHITECTURE_DOCS: ./context/architecture/<flow>.md, ...
FIGMA_FILE: <file key>  # Figma-pinned slices
NODE_IDS: <node id>, ...  # Figma-pinned slices
VISUAL_CAPTURE_PATHS: <png> <png> ...  # tester, when captures exist
DEVICE: <agistry resource id>  # the phone the orchestrator claimed for this stage
PR: #<n>  # pipeline-reviewer, once the draft PR exists
INVALIDATED: <decision or premise id>: <one line>  # with DESIGN_INVALIDATED
```

Take `WORKTREE`, `BRANCH` and `STORY_DIR` from the block; never rebuild them from `TASK_ID`. Intake's prompt is self-contained: full request text, acceptance criteria, constraints, known baseline/version context; answers to its `NEEDS_INPUT` go in a new invocation.

## Shape

| Level | When | Stages |
| --- | --- | --- |
| **trivial** | Single-file copy / config / typo / version bump. < 20 lines. No new contract. | intake → implementer → tester → pipeline-reviewer |
| **quick** | 1–3 files; a bug fix or small enhancement inside an existing flow doc's contracts. | as trivial |
| **standard** | Touches a contract (data model, single-writer, rendering, persistence, wire format, trust boundary). | intake → architect ⇄ critic → implementer (slice → slice review → finish) → tester → pipeline-reviewer |
| **complex** | Cross-flow, new flow, architecture-changing. | standard, with `DESIGN_EXPLORATION=YES` |

Intake classifies by the **riskiest contract touched**, not size. Security, schema, and breaking-API changes are at least standard, as is a task whose flow doc visibly contradicts the code.

- **Bugs reproduce first.** For `CLAIM: bug`, the tester's repro mode runs right after intake, before any design or code: it reproduces the symptom on `main`, finds the cause (for a regression, the change that introduced it), and sets `COMPLEXITY` from it, re-deriving `NEEDS_RESEARCH` and `DESIGN_EXPLORATION` when it changes.
- **Research before choices.** `NEEDS_RESEARCH=YES` (intake sets it when a product call shapes the contract or the work is complex): the researcher runs next (after the repro for a bug), writing `research.md`: what users need (issues, discussions, feedback, reviews, forums) and how comparable products solve it. Product-call defaults and the architect's hard choices cite it.
- **Planner** (`PLAN=YES`, set by intake or the architect) runs after the architect-critic only when sequencing is itself a risk: several PRs, a data migration, a native build change that must land in steps, or a feature-flag rollout. Otherwise the implementer sequences its own work.
- **Slicing.** When the projected diff exceeds ~1,500 lines or WHAT can't fit its length budget, the architect proposes slices and replies `NEEDS_INPUT`; each slice becomes its own task.

## Routing

Dispatch the next role from the returning verdict at once, with no prompt or approval gate. **Design entry** = intake `READY` (new task, not a bug), tester (repro) `REPRODUCED`, or researcher `DONE`; its rows apply once no row above them does.

| Stage | Verdict | Next |
| --- | --- | --- |
| intake | `NEEDS_INPUT` | stop; surface the questions |
| intake | `READY`, bug | tester, repro mode |
| intake (not a bug) or tester (repro) `REPRODUCED` | `NEEDS_RESEARCH=YES` | researcher |
| design entry | trivial / quick | implementer |
| design entry | standard / complex | architect (with `DESIGN_EXPLORATION=YES`, the design arena first) |
| researcher | `NEEDS_INPUT` (a contract-shaping product call, with its researched default) | stop; answers are logged as rulings in `decisions.md`, then route as for `DONE` |
| intake | `READY`, PR fix | orchestrator writes the fix brief → plan-critic (fix-brief mode) |
| architect | `DRAFTED` | architect-critic |
| architect-critic | `LGTM` | planner when `PLAN=YES`, else implementer |
| architect-critic | `HAS_CONCERNS` / `HAS_BLOCKERS` | architect (revision; max 2 rounds; concerns still open after round 2 proceed, listed in the reply) |
| planner | `DRAFTED` | plan-critic |
| plan-critic | `LGTM` | implementer |
| plan-critic | `HAS_CONCERNS` / `HAS_BLOCKERS` | the producer revises: planner for HOW, the orchestrator for a fix brief (max 2 rounds) |
| implementer | `SLICE_READY` | architect-reviewer, slice mode (Tracer slice) |
| architect-reviewer (slice) | `LGTM` / `HAS_FINDINGS` | implementer, to finish (findings first) |
| implementer | `COMPLETE` | tester |
| tester | `COMPLETE` | pipeline-reviewer (redesign slices: design-parity-reviewer first) |
| tester, post-PR mode | `COMPLETE` | the gates |
| tester | `IMPLEMENTATION_BUG` | implementer |
| design-parity-reviewer | `APPROVED` / `NEEDS_FIXES` | pipeline-reviewer / implementer (max 2 rounds) |
| pipeline-reviewer | `APPROVED` (with `PR`) | tester in post-PR mode when `evidence.md` has CI-APK rows; then the gates |
| `tools/pr-gates.sh` | `ci` PEND (exit 4) | wait (a watcher, `skills/start-task`); no attempt consumed |
| `tools/pr-gates.sh` | `ci` or `hygiene` FAIL (exit 1) | implementer (CI; hygiene in code or commits) or pipeline-reviewer (hygiene in PR text); max 2, then `BLOCKED` |
| `tools/pr-gates.sh` | exit 2 (usage or `gh` error) | `BLOCKED` |
| `tools/pr-gates.sh` | all PASS | independent review (`review-pr`) |
| review-pr | `NOT_READY` | as a gate FAIL; no round consumed |
| pipeline-reviewer | `REQUEST_CHANGES` | implementer |
| pipeline-reviewer | `ESCALATE` (branch already on `origin/main`) | stop; the merge gate was bypassed |
| any stage after intake | `DESIGN_INVALIDATED` | architect (amendment). Trivial / quick: the orchestrator re-classifies to standard and dispatches the architect in the same worktree |
| any stage | `NEEDS_INPUT` / `ESCALATE` / `BLOCKED` | stop |

## Autonomous-run contract

Stop only for:

- `NEEDS_INPUT` (each question with a recommended answer), `ESCALATE`, or `BLOCKED` (environment or tooling; design conflicts are `DESIGN_INVALIDATED`) from any stage
- `HAS_BLOCKERS` persisting after round 2 of a critic loop
- incomplete required independent review artifacts
- failed mandatory verification
- `BLOCKER` or `CONCERN` findings persisting after review round 2

The orchestrator sends a stop's questions to `operator` over agistry (AGENTS.md, Asking the operator); when a PM session runs the queue, to the PM first (`skills/pm`).

## Evidence plan

See [`evidence-and-decisions.md`](evidence-and-decisions.md).

## Decisions and product calls

See [`evidence-and-decisions.md`](evidence-and-decisions.md).

## Tracer slice

Standard and complex work: the implementer first commits the thinnest end-to-end slice of the WHAT's core path; `pocketpal-architect-reviewer` reviews the slice diff against the WHAT. A finding that contradicts a WHAT decision or premise comes back as `DESIGN_INVALIDATED`.

## Going back

`DESIGN_INVALIDATED` and restarts: see [`design-and-restarts.md`](design-and-restarts.md).

## Independent review loop

See [`review-and-finalization.md`](review-and-finalization.md).

## Finalization after the human merges

See [`review-and-finalization.md`](review-and-finalization.md).

## Design exploration

See [`design-and-restarts.md`](design-and-restarts.md).

## Redesign slices (Figma-pinned work)

For a task that implements a Figma node id, the implementer follows the `figma-implement` skill and the design-parity-reviewer runs as routed above (`docs/workflows/visual-capture.md`, Flavour C).
