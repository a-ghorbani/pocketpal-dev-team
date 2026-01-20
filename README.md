# PocketPal Dev Team

AI-powered autonomous development team for PocketPal AI. Takes issues/tasks and delivers implementations with tests.

## Quick Start

```bash
cd /Users/aghorbani/codes/pocketpal-dev-team

# Start a task
claude "Use pocketpal-orchestrator: <your task description>"
```

## Example Tasks

```bash
# Feature
claude "Use pocketpal-orchestrator: Add haptic feedback when sending messages"

# Bug fix
claude "Use pocketpal-orchestrator: Fix crash when loading large models on low-memory devices"

# Dependency upgrade
claude "Use pocketpal-orchestrator: Upgrade llama.rn to latest version"

# From GitHub issue
claude "Use pocketpal-orchestrator: Implement GitHub issue #123"
```

## Workflow

```
Your Task
    ↓
pocketpal-orchestrator    → Analyzes, classifies complexity
    ↓
pocketpal-planner         → Researches codebase, creates plan
    ↓
[YOU APPROVE PLAN]        → Review the story file
    ↓
pocketpal-implementer     → Writes code
    ↓
pocketpal-tester          → Writes and runs tests
    ↓
pocketpal-reviewer        → Quality checks
    ↓
[DRAFT PR]
```

## Agents

| Agent | Purpose |
|-------|---------|
| `pocketpal-orchestrator` | Entry point - analyzes tasks, routes to other agents |
| `pocketpal-planner` | Researches codebase, creates detailed implementation plans |
| `pocketpal-implementer` | Writes code following the plan |
| `pocketpal-tester` | Writes tests using PocketPal's testing patterns |
| `pocketpal-reviewer` | Verifies quality before PR |

## Invoke Agents Directly

```bash
# Just create a plan (no implementation)
claude "Use pocketpal-planner: Add dark mode support"

# Implement an existing story
claude "Use pocketpal-implementer: Implement story in workflows/stories/ISSUE-123.md"

# Write tests for recent changes
claude "Use pocketpal-tester: Write tests for the ModelSelector component"

# Review before PR
claude "Use pocketpal-reviewer: Review changes for issue #123"
```

## Parallel Development

Run multiple features simultaneously using git worktrees:

```bash
# Create worktrees (from pocketpal-ai)
cd /Users/aghorbani/codes/pocketpal-ai
git worktree add ../pocketpal-dev-team/worktrees/feature-A -b feature/A
git worktree add ../pocketpal-dev-team/worktrees/feature-B -b feature/B

# Run agents in separate terminals
cd /Users/aghorbani/codes/pocketpal-dev-team
claude "Use pocketpal-orchestrator: Task A - work in worktrees/feature-A/"
claude "Use pocketpal-orchestrator: Task B - work in worktrees/feature-B/"
```

## Autonomous Mode

Skip permission prompts for faster execution:

```bash
claude --dangerously-skip-permissions "Use pocketpal-orchestrator: <task>"
```

Safe commands are pre-allowed in `.claude/settings.json`. Dangerous commands (rm -rf, curl, .env access) are blocked.

## Project Structure

```
pocketpal-dev-team/
├── .claude/
│   ├── agents/           # Agent definitions
│   └── settings.json     # Permission rules
├── context/              # Codebase patterns & overview
├── workflows/stories/    # Implementation plans
├── worktrees/            # Git worktrees for parallel work
└── templates/            # Story file template
```

## Key Files

- `context/patterns.md` - Coding patterns (especially testing - read this!)
- `workflows/stories/` - Story files created by planner
- `.claude/settings.json` - Auto-approved commands

## Tips

1. **Be specific** - More detail in your task = better results
2. **Review plans** - Always check the story file before approving
3. **Check tests** - PocketPal has specific testing patterns (centralized mocks)
4. **Start small** - Test with simple tasks first
