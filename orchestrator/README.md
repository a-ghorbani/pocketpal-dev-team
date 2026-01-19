# PocketPal Dev Team Orchestrator

This folder contains setup and configuration for the AI development team.

## Quick Start

### 1. Agents are Ready

Custom agents are defined in `/.claude/agents/`:
- `pocketpal-orchestrator` - Entry point, task analysis
- `pocketpal-planner` - Creates implementation plans
- `pocketpal-implementer` - Writes code
- `pocketpal-tester` - Writes and runs tests
- `pocketpal-reviewer` - Quality gate before PR

### 2. Start a Development Task

From the PocketPal repo, invoke the orchestrator:

```bash
cd /Users/aghorbani/codes/pocketpal-ai

# Start with a GitHub issue
claude "Use pocketpal-orchestrator to analyze and implement GitHub issue #123"

# Start with a description
claude "Use pocketpal-orchestrator to implement: Add a dark mode toggle to settings"

# Start with a Linear ticket
claude "Use pocketpal-orchestrator to implement Linear ticket ABC-123"
```

### 3. Workflow

```
Orchestrator → Planner → [Human Approval] → Implementer → Tester → Reviewer → PR
```

**Human checkpoints:**
1. After Planner creates story - approve the implementation plan
2. After Reviewer approves - review and merge the PR

## Agent Invocation

You can invoke agents directly for specific tasks:

```bash
# Create a plan for a specific task
claude "Use pocketpal-planner to create a story for: [task description]"

# Implement an approved plan
claude "Use pocketpal-implementer to implement story ISSUE-123"

# Write tests for implemented code
claude "Use pocketpal-tester to write tests for the changes in ISSUE-123"

# Review before PR
claude "Use pocketpal-reviewer to review the implementation of ISSUE-123"
```

## Story Files

Plans are saved to `/workflows/stories/`:

```
workflows/stories/
├── ISSUE-123.md
├── ISSUE-456.md
└── STORY-20260119.md
```

## Configuration

### Agent Tools

| Agent | Tools |
|-------|-------|
| orchestrator | Read, Grep, Glob, Bash, WebFetch |
| planner | Read, Grep, Glob, Bash |
| implementer | Read, Grep, Glob, Bash, Edit, Write |
| tester | Read, Grep, Glob, Bash, Edit, Write |
| reviewer | Read, Grep, Glob, Bash |

### Model

All agents use `sonnet` by default for cost/speed balance.

For complex architectural decisions, you can override:
```bash
claude --model opus "Use pocketpal-planner for complex feature X"
```

## Troubleshooting

### Agent Not Found

Ensure you're in a directory where Claude Code can see the `.claude/agents/` folder:
- `/Users/aghorbani/codes/pocketpal-dev-team/` (where agents are defined)
- Or symlink/copy to your working directory

### Context Issues

If agents seem to lack context:
1. Check that context files exist in `/context/`
2. Ensure PocketPal repo is accessible at expected path
3. Verify story file exists in `/workflows/stories/`

### Test Failures

If tester produces wrong patterns:
1. Ensure it read `jest/setup.ts` and `jest/test-utils.tsx`
2. Check the patterns doc in `/context/patterns.md`
3. Review the "CRITICAL MISTAKES TO AVOID" section

## Phase 2: Parallel Execution (Coming Soon)

Future enhancements will include:
- Git worktree management for parallel work
- Task queue for multiple issues
- Progress dashboard
- 2-10 concurrent agents
