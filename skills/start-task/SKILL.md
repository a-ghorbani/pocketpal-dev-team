---
name: start-task
description: Start a new PocketPal delivery task from a work-item reference (any tracker) or a free-form description. Resolves the reference per context/issue-tracking.md, then runs the delivery loop through implementation, draft PR, independent review, and review-fix rounds when needed.
user-invocable: true
argument-hint: "[work reference or description]"
---

# Start Task

You are the top-level delivery controller for one PocketPal task. You dispatch every stage role yourself and route between them. Read [`docs/workflows/pipeline.md`](../../docs/workflows/pipeline.md) first: it is your runbook.

Task: $ARGUMENTS (if that placeholder is not substituted, the task is the argument the user gave with the invocation).

## 1. Resolve the reference

Resolve the reference by its shape, per [`context/issue-tracking.md`](../../context/issue-tracking.md):

- **GitHub issue** (`#123`): `gh issue view <n> --repo a-ghorbani/pocketpal-ai --json title,body,labels`.
- **Plane** (`POC-123`, …): `./tools/plane show <ref>`.
- **Linear** (`FOU-123`, legacy): `./tools/linear.sh issues`, then match the identifier.
- **Anything else**: a free-form description.

## 2. Dispatch intake with a self-contained brief

```text
Use pocketpal-intake: <title>

Request:
<the issue / work-item body verbatim, or the description>

Metadata:
- Source: github | plane | linear | description
- GitHub issue: #<n>             # github only
- Tracker ID: <identifier>       # internal: keep out of every public GitHub artifact
- Labels / Priority / Status: <from the tracker, when present>

Repository: ./repos/pocketpal-ai
```

## 3. Run the pipeline

Once intake returns `TASK_ID`, join agistry as `<TASK_ID>:orchestrator` (the agistry skill), so the operator's replies reach this task even if the session is replaced.

Route on each stage's `VERDICT` by the routing table in `pipeline.md`. Beyond the table:

- **Design arena** (`DESIGN_EXPLORATION=YES`): before the architect's first draft, write the handoff block to `<STORY_DIR>/handoff.txt`, run `tools/design-arena.sh run <STORY_DIR>` in the background (it takes up to a few hours), then dispatch the architect in merge mode with its exit code.
- **Slice review** (`SLICE_READY`): give `pocketpal-architect-reviewer` the slice's commit range.
- **`DESIGN_INVALIDATED`**: check the restart triggers under "Going back" before dispatching the architect's amendment.
- **Questions for the operator** (AGENTS.md, Asking the operator): send a stage's `NEEDS_INPUT` questions and its defaulted product calls to `operator` in one message, each with its default and the research behind it, or to the PM when a PM dispatched this task. Contract-shaping calls wait for the reply; the rest proceed on their defaults. Log each answer in `decisions.md` as a ruling, then resume.
- **Gates**: wait on `tools/pr-gates.sh <PR>` with a watcher that outlives your turn, not a poll-and-exit.
- **`REQUEST_CHANGES`**: follow "Independent review loop" in `pipeline.md`. You write the fix brief into the PR-fix story intake created, and you are the only writer of review dismissals in `decisions.md`.

Stop only on the conditions under "Autonomous-run contract" in `pipeline.md`. When a PM session dispatched this task, send stops to the PM over agistry rather than to the operator. Otherwise finish with `APPROVE`, and the human reviews and merges.

## 4. Keep the tracker current

When the task came from an internal tracker, its work item is the task's status for the PM. At each milestone, post one comment and move the state, using that tracker's commands from "Status updates" in [`context/issue-tracking.md`](../../context/issue-tracking.md):

| Milestone | State | Comment |
| --- | --- | --- |
| Intake done | In Progress | `[started] <complexity> · <TASK-ID>` |
| Spec approved | | `[spec] approved` |
| PR opened | In Review | `[pr] #<n> · head <sha7>` |
| Review verdict | | `[review] <verdict> · round <R> · head <sha7>` |
| Stopped on a stop condition | | `[blocked] <what is needed, from whom>` |
| Final `APPROVE` | | `[ready] #<n> · head <sha7> · CI <status>` |

Each comment is one line: facts only, no reasoning or explanation. Detail lives in the PR and the story. Skip this step for GitHub issues and free-form descriptions.
