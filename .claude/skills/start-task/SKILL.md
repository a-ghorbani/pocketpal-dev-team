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

Then use the `pocketpal-orchestrator` agent with the issue context:

```
Use pocketpal-orchestrator to analyze GitHub issue #[number]

Issue Title: [title from gh]
Issue Body: [body from gh]
Labels: [labels from gh]

Repository: /Users/aghorbani/codes/pocketpal-ai
```

## For Description

Use the `pocketpal-orchestrator` agent directly:

```
Use pocketpal-orchestrator: $ARGUMENTS

Repository: /Users/aghorbani/codes/pocketpal-ai
```

## What Happens Next

The orchestrator will:
1. Generate a task ID (TASK-YYYYMMDD-HHMM)
2. Create a worktree at `worktrees/TASK-xxx`
3. Create a feature branch
4. Copy secrets/env files
5. Classify complexity (quick/standard/complex)
6. Route to planner with worktree context

After the planner creates a story file, you'll be asked to approve before implementation begins.

## Workflow

```
/start-task → orchestrator → planner → [HUMAN APPROVAL] → implementer → tester → reviewer → PR
```
