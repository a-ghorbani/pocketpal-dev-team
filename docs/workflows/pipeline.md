# Delivery Pipeline Playbook

Orchestrator runbook for the top-level `/start-task` session (and the PR-fix loop it drives): how to run a task end to end. The always-on invariants every agent obeys are in `AGENTS.md`.

## Autonomous-run contract

After each stage returns, the calling session immediately invokes the next agent in the chain. Do NOT use `AskUserQuestion` or any other interactive prompt between stages. There is no human approval gate between stages. Stop ONLY for:

- `NEEDS_INPUT` from intake (unanswered clarifications in the brief)
- `HAS_BLOCKERS` persisting after round 2 of either critic loop
- `ESCALATE` from any review stage
- incomplete required independent review artifacts
- failed mandatory verification
- `BLOCKER` or `CONCERN` findings persisting after round 2 of the independent review/fix loop

Keep the four-stage pipeline intact: **Intent → WHAT → HOW → Implementation**. The delivery loop may wrap it, but must not collapse implementation and independent review into the same role.

## Pipeline

Pipeline (each arrow is "produces and hands off to"):

```text
Issue
  │
  ▼
intake ── intent-brief.md  (builds a self-contained brief; emits `NEEDS_INPUT` and stops if required answers are missing; classifies)
  │
  ├── trivial ───────────────────────────────────────────────────────┐
  │                                                                  │
  ├── quick ──────────────────────────────────────────┐              │
  │                                                   │              │
  └── standard / complex                              │              │
              │                                       │              │
              ▼                                       │              │
       architect ── what.md ──┐                       │              │
              ▲               │                       │              │
              │ revise on     ▼                       │              │
              └── architect-critic                    │              │
                       │                              │              │
                       │ LGTM                         │              │
                       ▼                              ▼              │
                     planner ── how.md ──┐ ◄──────────┘              │
                       ▲                 │                           │
                       │ revise on       ▼                           │
                       └── plan-critic ──┘                           │
                              │                                      │
                              │ LGTM                                 │
                              │ (or ARCHITECTURE_DRIFT → architect)  │
                              ▼                                      │
                        implementer ◄────────────────────────────────┘
                              │      (code + commits + architecture-doc update)
                              ▼
                            tester ── tests + coverage + visual captures
                              │
                              ▼
                       pipeline-reviewer ── draft PR (+ visual-evidence comment) | REQUEST_CHANGES
                              │
                              ▼
                       independent review ── final.md
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
          review feedback              HUMAN REVIEW & MERGE
          intake + PR-fix
                │
                └────────────── back to implementation pipeline
```

The delivery loop is coordinated by the top-level `/start-task` session. It starts the implementation pipeline, invokes the independent review pipeline after a draft PR exists, normalizes `REQUEST_CHANGES` into a review-feedback artifact, and routes fixes through the PR-fix pipeline. The independent reviewer remains separate from the implementation agents.

## Stage outputs

| Stage | Agent | Output |
| --- | --- | --- |
| Intent | `pocketpal-intake` | `workflows/stories/<TASK-ID>/intent-brief.md` or a `NEEDS_INPUT` stop with explicit unanswered questions |
| WHAT | `pocketpal-architect` | `workflows/stories/<TASK-ID>/what.md` (delta on `context/architecture/<flow>.md`) |
| WHAT review | `pocketpal-architect-critic` | LGTM / HAS_CONCERNS / HAS_BLOCKERS |
| HOW | `pocketpal-planner` | `workflows/stories/<TASK-ID>/how.md` |
| HOW review | `pocketpal-plan-critic` | LGTM / HAS_CONCERNS / HAS_BLOCKERS / ARCHITECTURE_DRIFT |
| Implementation | `pocketpal-implementer` | code + commits + architecture-doc update |
| Test | `pocketpal-tester` | tests + coverage + visual captures + durable command/results notes |
| Final review | `pocketpal-pipeline-reviewer` | draft PR or REQUEST_CHANGES, with artifact-backed verification evidence + visual-evidence PR comment |
| Independent review | `review-pr` skill / `pocketpal-code-reviewer` + role reviewers | `workflows/reviews/<TARGET-ID>/round-<N>/final.md` |
| Review feedback intake | `/start-task` top-level session | `workflows/stories/<TASK-ID>/review-feedback-round-<N>.md` |

## Headless invocation contract

- Every intake invocation must be a self-contained brief. Include the full request text, acceptance criteria, constraints, and any known baseline/version context in the prompt itself.
- If information is missing, intake must stop with `NEEDS_INPUT:` and list the exact unanswered questions. It must not guess, classify, or route downstream until a new invocation supplies those answers.

## Complexity matrix

| Level | When | Pipeline applied |
| --- | --- | --- |
| **trivial** | Single-file copy / config / typo / version bump. < 20 lines. No new contract. | Intent → Implementer (skip WHAT, HOW, plan-critic). |
| **quick** | 1–3 files. Bug fix or small enhancement that doesn't change a contract; existing flow doc covers the area. | Intent → Planner → Plan-critic → Implementer (skip WHAT). |
| **standard** | Touches a contract (data model, single-writer, rendering, persistence, wire format). Multi-file. Existing flow doc may need a delta. | Full pipeline. |
| **complex** | Cross-flow, new flow, architecture-changing. Likely creates a new flow doc. | Full pipeline; expect both critic loops to use the full 2-round budget. |

Intake picks the level once the brief is written. If `Status: approved` (no clarifications needed) it classifies and emits the first handoff; if `Status: needs-input` it emits `NEEDS_INPUT` and stops. When in doubt, classify up.

## Exploration policy

Design and plan exploration are lightweight candidate passes before the final contract artifacts:

- **Design exploration** is required for complex tasks and optional for standard tasks with competing architecture shapes, persistence/migration risk, native/model execution changes, security/trust-boundary changes, or cross-store ownership uncertainty.
- **Plan exploration** is required for complex tasks and optional for standard tasks with risky sequencing, broad verification uncertainty, native build changes, migrations, feature-flag rollout, or cross-flow commit boundaries.
- Candidate artifacts live beside the story as `design-candidate-*.md` or `plan-candidate-*.md`.
- Critics review only the synthesized `what.md` or `how.md`, not every candidate.
- Final WHAT/HOW stay concise: WHAT may include bounded alternatives bullets; HOW uses a one-line sequencing note.

## Critic loop semantics

Both critic loops follow the same shape:

- **LGTM** → producer's output advances to the next stage.
- **HAS_CONCERNS / HAS_BLOCKERS** → back to the same producer (architect or planner) in revision mode.
- **ARCHITECTURE_DRIFT** (plan-critic only) → back to the **architect**, not the planner. A bug in WHAT is fixed in WHAT.
- **Max 2 critic rounds.** If round 2 still has BLOCKERs, escalate to human.
- The critic is invoked with **paths only** — never the producer's reasoning. It forms its own view from the codebase.

## Independent review loop

After `pocketpal-pipeline-reviewer` opens a draft PR, the top-level `/start-task` session invokes the independent review pipeline:

```text
review-pr <PR number>
```

Review output is durable:

```text
workflows/reviews/PR-<n>/round-<N>/final.md
```

If the verdict is `REQUEST_CHANGES`, the top-level `/start-task` session creates:

```text
workflows/stories/<TASK-ID>/review-feedback-round-<N>.md
```

Only `BLOCKER` and `CONCERN` findings are mandatory fix scope. `SUGGESTION` findings are out of scope unless required by a mandatory fix. The PR-fix pipeline consumes the feedback artifact and the independent review repeats. Max 2 external review/fix rounds, then escalate if blockers or concerns persist.

## Disambiguation: similar agent names

| Agent | When | What it reviews |
| --- | --- | --- |
| `pocketpal-architect` | After intent, before HOW | Produces `what.md` |
| `pocketpal-architect-critic` | After WHAT drafted | `what.md` (design) |
| `pocketpal-architect-reviewer` | During PR review | CODE diffs (architecture lens) |
| `pocketpal-plan-critic` | After HOW drafted | `how.md` (plan) |
| `pocketpal-pipeline-reviewer` | After impl + tests | Everything; gates draft PR |
| `pocketpal-code-reviewer` | Standalone | Branch or PR, independent of pipeline state |

Pipeline progression: **architect → architect-critic → planner → plan-critic → implementer → tester → pipeline-reviewer**.
