---
name: start-task
description: Start a new development task for PocketPal AI from a GitHub issue or description. Creates worktree, analyzes requirements, routes to planner.
user-invocable: true
argument-hint: "[#issue-number or description]"
---

# Start Task Workflow

You are starting a new development task for PocketPal AI.

## Input

Task: $ARGUMENTS

## Determine Input Type

Check if the input is:

1. **GitHub Issue**: Starts with `#` followed by a number (e.g., `#123`, `#456`)
2. **Description**: Any other text (e.g., "Add dark mode toggle")

## For GitHub Issue (e.g., #123)

First, fetch the issue details:

```bash
gh issue view [number] --repo pocketpal-ai/pocketpal-ai --json title,body,labels,assignees
```

Then use the `pocketpal-orchestrator` agent with a self-contained brief built from the issue context:

```
Use pocketpal-orchestrator: [title from gh]

Request:
[paste the issue body verbatim so the brief stands alone]

Metadata:
- GitHub issue: #[number]
- Labels: [labels from gh]

Repository: ./repos/pocketpal-ai
```

## For Description

Use the `pocketpal-orchestrator` agent directly:

```
Use pocketpal-orchestrator: $ARGUMENTS

Repository: ./repos/pocketpal-ai
```

## What Happens Next

The orchestrator will:

1. Generate a task ID (TASK-YYYYMMDD-HHMM)
2. Create a worktree at `worktrees/TASK-xxx` using the repo helper scripts
3. Create a feature branch
4. Sync the allowlisted gitignored config/env files into the worktree
5. Stop with `NEEDS_INPUT` if required information is missing
6. Classify complexity
7. Route with worktree context when the brief is approved

After the planner creates a story file, the story critic reviews it automatically. Implementation proceeds if the critic approves (LGTM). Human is involved when blockers persist after revision or when the orchestrator returns `NEEDS_INPUT`.

## Workflow

```
/start-task → orchestrator → planner → critic (review-revise) → implementer → tester → reviewer → PR
```
