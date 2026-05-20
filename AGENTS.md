# Agent Instructions

This repo is the workflow control plane for PocketPal AI. The target app code is in `repos/pocketpal-ai`, but that submodule is read-only.

## Non-Negotiables

- Never edit, build, commit, or switch branches inside `repos/pocketpal-ai/`. Use it only as the source repo for creating worktrees and reading source.
- All task work happens in `worktrees/<TASK-or-PR>/` on a non-`main` branch.
- Never create a worktree from the dev-team repo itself. Worktrees come from `repos/pocketpal-ai`.
- Never remove worktrees with raw `git worktree remove`, `git worktree prune`, `rm -r`, or `rmdir`. Use `./tools/remove-worktree.sh <name> --yes` only when the user explicitly asks for cleanup.
- Never bulk-copy secrets or config. Use only the allowlisted sync in `./tools/sync-worktree-config.sh` or `./tools/create-worktree.sh`.
- Never implement without the artefacts the complexity level requires (see Workflow).
- Keep the four-stage pipeline intact: **Intent → WHAT → HOW → Implementation**.
- `NATIVE_CHANGES=YES` requires `pod install` + iOS build + Android build before the work can be called ready.
- Every PR that changes behaviour described in `context/architecture/*.md` must update the relevant doc **in the same PR**. Drift is forbidden.
- **Run the pipeline autonomously.** After each stage returns, the calling session immediately invokes the next agent in the chain. Do NOT use `AskUserQuestion` or any other interactive prompt between stages. There is no human approval gate between stages. Stop ONLY for:
  - `NEEDS_INPUT` from the orchestrator (unanswered clarifications in the brief)
  - `HAS_BLOCKERS` persisting after round 2 of either critic loop

## Workflow

Pipeline (each arrow is "produces and hands off to"):

```text
Issue
  │
  ▼
orchestrator ── intent-brief.md  (builds a self-contained brief; emits `NEEDS_INPUT` and stops if required answers are missing; classifies)
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
                            tester ── tests + coverage
                              │
                              ▼
                       pipeline-reviewer ── draft PR | REQUEST_CHANGES
                              │
                              ▼
                       HUMAN REVIEW & MERGE
```

### Stage outputs

| Stage | Agent | Output |
| --- | --- | --- |
| Intent | `pocketpal-orchestrator` | `workflows/stories/<TASK-ID>/intent-brief.md` or a `NEEDS_INPUT` stop with explicit unanswered questions |
| WHAT | `pocketpal-architect` | `workflows/stories/<TASK-ID>/what.md` (delta on `context/architecture/<flow>.md`) |
| WHAT review | `pocketpal-architect-critic` | LGTM / HAS_CONCERNS / HAS_BLOCKERS |
| HOW | `pocketpal-planner` | `workflows/stories/<TASK-ID>/how.md` |
| HOW review | `pocketpal-plan-critic` | LGTM / HAS_CONCERNS / HAS_BLOCKERS / ARCHITECTURE_DRIFT |
| Implementation | `pocketpal-implementer` | code + commits + architecture-doc update |
| Test | `pocketpal-tester` | tests + coverage + durable command/results notes |
| Final review | `pocketpal-pipeline-reviewer` | draft PR or REQUEST_CHANGES, with artifact-backed verification evidence |

### Headless invocation contract

- Every orchestrator invocation must be a self-contained brief. Include the full request text, acceptance criteria, constraints, and any known baseline/version context in the prompt itself.
- If information is missing, the orchestrator must stop with `NEEDS_INPUT:` and list the exact unanswered questions. It must not guess, classify, or route downstream until a new invocation supplies those answers.

### Complexity matrix

| Level | When | Pipeline applied |
| --- | --- | --- |
| **trivial** | Single-file copy / config / typo / version bump. < 20 lines. No new contract. | Intent → Implementer (skip WHAT, HOW, plan-critic). |
| **quick** | 1–3 files. Bug fix or small enhancement that doesn't change a contract; existing flow doc covers the area. | Intent → Planner → Plan-critic → Implementer (skip WHAT). |
| **standard** | Touches a contract (data model, single-writer, rendering, persistence, wire format). Multi-file. Existing flow doc may need a delta. | Full pipeline. |
| **complex** | Cross-flow, new flow, architecture-changing. Likely creates a new flow doc. | Full pipeline; expect both critic loops to use the full 2-round budget. |

The orchestrator picks the level once the brief is written. If `Status: approved` (no clarifications needed) it classifies and routes immediately; if `Status: needs-input` it emits `NEEDS_INPUT` and stops. When in doubt, classify up.

### Critic loop semantics

Both critic loops follow the same shape:

- **LGTM** → producer's output advances to the next stage.
- **HAS_CONCERNS / HAS_BLOCKERS** → back to the same producer (architect or planner) in revision mode.
- **ARCHITECTURE_DRIFT** (plan-critic only) → back to the **architect**, not the planner. A bug in WHAT is fixed in WHAT.
- **Max 2 critic rounds.** If round 2 still has BLOCKERs, escalate to human.
- The critic is invoked with **paths only** — never the producer's reasoning. It forms its own view from the codebase.

## Operating Rules

### Worktree isolation

Every implementation, test, or PR review of PocketPal app code happens in a dedicated worktree under `worktrees/`. The submodule is only the source used to create worktrees and read source code.

Agents stop and report when:

- `pwd` is inside `repos/pocketpal-ai/`
- the current branch is `main` or `master`
- expected `WORKTREE`, `BRANCH`, or story context is missing
- a requested action would mutate, build, or commit inside the submodule

### Submodule read-only

`repos/pocketpal-ai/` is read-only. Agents must never edit, switch branches, commit, build, or test inside it; never reference its build artifacts; never upload its files as generated assets. Builds, tests, screenshots, and reports happen in a worktree.

### Story gate

Implementation requires the artefacts the complexity level mandates. Trivial: `intent-brief.md`. Quick: + `how.md`. Standard / complex: + `what.md`.

### Architecture library

`context/architecture/` holds the cumulative architecture truth, one file per flow. See `context/architecture/README.md` for the lifecycle.

- Standard / complex stories produce `what.md` as a **delta** on the relevant flow doc.
- The implementer absorbs the approved delta into the flow doc in the **same PR** that lands the code (a step in `how.md`).
- Drift is treated as a bug. The architect runs a drift check at the start of every standard / complex story.

### Native verification

Tasks touching `package.json`, native modules, `ios/`, `android/`, Podfile, or build.gradle are `NATIVE_CHANGES=YES`. Required before "ready": `pod install`, an iOS build, an Android build. Missing native verification is a blocking review issue.

### Secrets, config, cleanup

- Do not read, copy, or bulk-sync `.env` files or private config by hand. Use only the allowlisted sync tools.
- Do not remove worktrees outside `./tools/remove-worktree.sh <name> --yes`, and only when the user explicitly asks.

### Subagent authorisation for reviews

For PR reviews and high-risk code reviews, the user explicitly authorises delegated (e.g. Codex to use `spawn_agent`) subreviews (architect-reviewer, QA, security, performance, mobile, data, UX, local-invariants, etc.) as required by the review workflow.

## GitHub conventions

PR / issue / comment signature:

```text
Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team)
```

Commits: never add `Co-Authored-By` trailers (hook-enforced).

Titles: `[Bug]: ...` (label `bug`), `[Feat]: ...` (label `enhancement`), or a short PR description under 70 chars.

## Worktree commands

```bash
# New task
./tools/create-worktree.sh TASK-YYYYMMDD-HHMM
# Defaults: worktree=worktrees/TASK-..., branch=feature/TASK-..., ref=origin/main

# PR branch (fetch first)
./tools/create-worktree.sh PR-490 --branch pr-490 --ref pr-490

# Detached E2E from existing remote ref
./tools/create-worktree.sh PR-490-e2e --detach --ref origin/my-pr-branch

# Re-sync allowlisted config into an existing worktree
./tools/sync-worktree-config.sh ./worktrees/TASK-YYYYMMDD-HHMM

# Remove a worktree (only when the user explicitly asks)
./tools/remove-worktree.sh TASK-YYYYMMDD-HHMM --yes [--force]
```

## Naming and layout

| Type | Worktree | Branch | Story directory |
| --- | --- | --- | --- |
| New task | `worktrees/TASK-YYYYMMDD-HHMM` | `feature/TASK-YYYYMMDD-HHMM` | `workflows/stories/TASK-YYYYMMDD-HHMM/` |
| PR fix | `worktrees/PR-<n>` | `pr-<n>` | `workflows/stories/PR-<n>-fix/` |
| PR E2E | `worktrees/PR-<n>-e2e` | detached | n/a |

Inside a story directory:

```
intent-brief.md    # always
what.md            # standard / complex only
how.md             # quick / standard / complex (not trivial)
```

## Key references

- Templates: `templates/{intent,what,how}-template.md`
- Architecture library: `context/architecture/README.md`
- Project context: `context/patterns.md`, `context/pocketpal-overview.md`
- Standards: `docs/standards/code-review.md`, `docs/workflows/visual-capture.md`

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
