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

## Prerequisites

This skill requires Linear integration. Ensure `LINEAR_API_KEY` is set in `.env`:
```bash
# .env
LINEAR_API_KEY=lin_api_xxxxx
```

## Step 1: Find the Action

Search for the action in Linear using the CLI tool:

```bash
# List all issues (actions)
./tools/linear.sh issues

# Or search in specific project
./tools/linear.sh issues [project_id]
```

Find the action that best matches "$ARGUMENTS" (case-insensitive, partial match OK).

## Step 2: Extract Action Context

From the matching Linear issue, extract:
- **Title**: The issue title
- **Priority**: Issue priority (1=urgent, 4=low)
- **Status**: Current workflow state
- **Description**: Full description with context
- **Identifier**: Linear issue ID (e.g., PPT-123)

You can fetch full issue details with:
```bash
./tools/linear.sh query "{ issue(id: \"<issue_id>\") { id identifier title description priority state { name } } }"
```

## Step 3: Route to Orchestrator

Use the `pocketpal-orchestrator` agent with the extracted context:

```
Use pocketpal-orchestrator: [Action Title]

Context from Linear:
- Linear ID: [identifier]
- Priority: [priority]
- Status: [status]

Description:
[description from Linear issue]

Repository: ./repos/pocketpal-ai
```

## What Happens Next

The orchestrator will:
1. Create a worktree for this action
2. Classify complexity based on the description
3. Route to planner to create a story file
4. Story will include Linear context for traceability

## Example

Input: `/start-action "lifecycle guard"`

Searches Linear issues, finds: "PPT-42: Fix UnknownCppException/SIGSEGV Crashes"

Extracts:
- Description: Add lifecycle guard to prevent context release during inference
- Priority: 1 (urgent)
- Status: In Progress

Routes to orchestrator with full context.

## Without Linear API Key

If `LINEAR_API_KEY` is not set, this skill will not work. You can:
1. Add your Linear API key to `.env`
2. Or use `/start-task` with a manual description instead
