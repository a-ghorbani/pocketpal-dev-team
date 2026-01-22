---
name: start-action
description: Start work on an action from the action-tracker. Searches for matching action by title and extracts context for the orchestrator.
user-invocable: true
argument-hint: "[action title or partial match]"
---

# Start Action Workflow

You are starting work on an action from the action-tracker.

## Input
Action search: $ARGUMENTS

## Step 1: Find the Action

Search for the action in the action-tracker files:

```
Read: /Users/aghorbani/codes/founder-advisory-board/action-tracker/in-progress.md
Read: /Users/aghorbani/codes/founder-advisory-board/action-tracker/accepted.md
```

Find the action that best matches "$ARGUMENTS" (case-insensitive, partial match OK).

## Step 2: Extract Action Context

From the matching action, extract:
- **Title**: The action title (### heading)
- **Priority**: P0/P1/P2
- **Status**: Current state
- **Next step**: Immediate action needed
- **Action Items**: Sub-tasks with checkboxes
- **Details**: Any additional context
- **Related**: Links to decisions, analysis files

## Step 3: Read Related Context

If the action has **Related** links, read those files to get full context:
- Decision logs in `decision-log/`
- Analysis in `shared-context/`

## Step 4: Route to Orchestrator

Use the `pocketpal-orchestrator` agent with the extracted context:

```
Use pocketpal-orchestrator: [Action Title]

Context from action-tracker:
- Priority: [priority]
- Status: [status]
- Next step: [next step]

Action Items:
[list of action items]

Details:
[details from action]

Related Context:
[content from related files if any]

Repository: /Users/aghorbani/codes/pocketpal-ai
```

## What Happens Next

The orchestrator will:
1. Create a worktree for this action
2. Classify complexity based on action items
3. Route to planner to create a story file
4. Story will include action-tracker context for continuity

## Example

Input: `/start-action "lifecycle guard"`

Matches: "Fix UnknownCppException/SIGSEGV Crashes" (contains "lifecycle guard" in action items)

Extracts:
- Next step: Add lifecycle guard to prevent context release during inference
- Action Items: Add lifecycle guard in ModelStore.ts, Add breadcrumb logging, etc.

Routes to orchestrator with full context.
