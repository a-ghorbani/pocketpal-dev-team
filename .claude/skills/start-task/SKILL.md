---
name: start-task
description: Start a new PocketPal delivery task from a work-item reference (any tracker) or a free-form description. Resolves the reference per context/issue-tracking.md, then runs the delivery loop through implementation, draft PR, independent review, and review-fix rounds when needed.
user-invocable: true
argument-hint: "[work reference or description]"
---

# Start Task Workflow

You are the top-level delivery controller for a new PocketPal AI task. This skill owns the orchestration and invokes stage agents directly from the current session.

## Input

Task: $ARGUMENTS

## Determine input type — resolve the reference

Resolve the reference per **[`context/issue-tracking.md`](../../../context/issue-tracking.md)**, which lists each reference shape, its tracker, and how to fetch it. Then hand off to `pocketpal-intake` with a `Source:` + `Tracker ID:` tag. Internal tracker IDs must never appear in public GitHub artifacts.

## For GitHub Issue (e.g., #123)

First, fetch the issue details:

```bash
gh issue view [number] --repo pocketpal-ai/pocketpal-ai --json title,body,labels,assignees
```

Then invoke `pocketpal-intake` with a self-contained brief built from the issue context:

```
Use pocketpal-intake: [title from gh]

Request:
[paste the issue body verbatim so the brief stands alone]

Metadata:
- Source: github
- GitHub issue: #[number]
- Labels: [labels from gh]

Repository: ./repos/pocketpal-ai
```

## For an internal-tracker reference

Fetch the work item with its tracker's tool:

- Plane: `./tools/plane.sh show <ref>`
- Linear (legacy): `./tools/linear.sh issues`, then match the identifier

Extract the title, priority, status, description, and identifier from the output. Then invoke `pocketpal-intake` with a self-contained brief — mirror the GitHub handoff structure so the brief stands alone:

```
Use pocketpal-intake: [title from tracker]

Request:
[paste the work-item description verbatim so the brief stands alone]

Metadata:
- Source: plane          # or: linear
- Tracker ID: [identifier]   # internal ID — keep out of public GitHub artifacts (PR title/body/comments, commits)
- Priority: [priority from tracker]
- Status: [status from tracker]

Repository: ./repos/pocketpal-ai
```

## For Description

Invoke `pocketpal-intake` directly:

```
Use pocketpal-intake: $ARGUMENTS

Repository: ./repos/pocketpal-ai
```

## What Happens Next

As the top-level session, continue the workflow after each stage returns:

1. Invoke `pocketpal-intake`.
2. Let the implementation pipeline run through the selected path:
   - trivial: Intent → Implementer
   - quick: Intent → Planner → Plan-Critic → Implementer
   - standard / complex: Intent → optional design exploration → WHAT → Architect-Critic → optional plan exploration → HOW → Plan-Critic → Implementer
3. Run tester and `pocketpal-pipeline-reviewer`.
4. Open or locate the draft PR when the pipeline approves.
5. Invoke the independent review pipeline with `/review-pr <PR>`.
6. Read `workflows/reviews/PR-<N>/round-<R>/final.md`.
7. If review returns `REQUEST_CHANGES`, create `workflows/stories/<TASK-ID>/review-feedback-round-<R>.md` from `templates/review-feedback-template.md`.
8. Route mandatory `BLOCKER` and `CONCERN` findings through the PR-fix pipeline by invoking `pocketpal-intake` with the feedback artifact.
9. Repeat independent review after fixes, max 2 external review/fix rounds.

Human involvement is required when `NEEDS_INPUT`, `ESCALATE`, incomplete required review artifacts, failed mandatory verification, or persistent blockers/concerns after the allowed rounds occur.

## Workflow

```
/start-task
  → implementation pipeline
  → draft PR
  → independent review pipeline
  → feedback intake + PR-fix loop if needed
  → APPROVE / ESCALATE
```
