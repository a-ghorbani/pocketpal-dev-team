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
