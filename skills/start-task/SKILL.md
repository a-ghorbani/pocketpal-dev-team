---
name: start-task
description: Start a new PocketPal delivery task from a work-item reference (any tracker) or a free-form description. Resolves the reference per context/issue-tracking.md, then runs the delivery loop through implementation, draft PR, independent review, and review-fix rounds when needed.
user-invocable: true
argument-hint: "[work reference or description]"
---

# Start Task

You are the top-level delivery controller for one PocketPal task. You dispatch every stage role yourself and route between them. Read [`docs/workflows/pipeline.md`](../../docs/workflows/pipeline.md) first; it holds the dispatch mechanics, the handoff block, the routing table, the stop conditions, and the critic-loop rules.

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

From here on, route on each stage's `VERDICT` using the routing table in `pipeline.md`. Pass the latest handoff block verbatim to each role. Critics get paths only, never the producer's reasoning.

Once the pipeline-reviewer returns `APPROVED` with a `PR`:

1. Run the independent review: the `review-pr` skill on that PR. Read `workflows/reviews/PR-<n>/round-<R>/final.md`.
2. If the verdict is `REQUEST_CHANGES`:
   - write `<STORY_DIR>/review-feedback-round-<R>.md` from `templates/review-feedback-template.md`, where only BLOCKER and CONCERN findings are fix scope;
   - dispatch intake with that artifact and `PR #<n>` for the PR-fix loop;
   - run the pipeline again, then the review again.
3. Allow at most 2 review/fix rounds, then escalate.

Stop only on the conditions listed under "Autonomous-run contract" in `pipeline.md`. Otherwise finish with `APPROVE`, and the human reviews and merges.

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
