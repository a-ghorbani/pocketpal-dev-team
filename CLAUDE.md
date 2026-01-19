# PocketPal Dev Team

AI-powered autonomous development team for PocketPal AI.

## Overview

This project contains the agent definitions, workflows, and orchestration logic for an AI development team that can:
- Take GitHub issues or Linear tickets
- Research the codebase and create implementation plans
- Implement features/fixes with proper tests
- Open draft PRs for human review
- Scale to 10-20 parallel agents working on different features (Phase 2+)

## Project Structure

```
pocketpal-dev-team/
├── .claude/
│   └── agents/              # Claude Code custom agent definitions
│       ├── pocketpal-orchestrator.md
│       ├── pocketpal-planner.md
│       ├── pocketpal-implementer.md
│       ├── pocketpal-tester.md
│       └── pocketpal-reviewer.md
├── context/                 # Shared context for PocketPal
│   ├── pocketpal-overview.md
│   └── patterns.md          # Coding & testing patterns (CRITICAL)
├── workflows/
│   └── stories/             # Story files (implementation plans)
├── templates/
│   └── story-template.md    # Template for new stories
├── worktrees/               # Git worktrees for parallel development
│   └── README.md            # Instructions for creating worktrees
├── orchestrator/
│   └── README.md            # Usage instructions
└── docs/
    └── research/            # Research and analysis
```

## Quick Start

### Start a Development Task

From this directory or pocketpal-ai:

```bash
# Analyze and implement a GitHub issue
claude "Use pocketpal-orchestrator to analyze GitHub issue #123"

# Start with a description
claude "Use pocketpal-orchestrator: Add dark mode toggle to settings"

# Create a plan only
claude "Use pocketpal-planner to create a story for: [description]"
```

### Workflow

```
Issue/Prompt
    ↓
pocketpal-orchestrator  (classify, extract requirements)
    ↓
pocketpal-planner       (research, create story file)
    ↓
[HUMAN APPROVAL]        (review and approve plan)
    ↓
pocketpal-implementer   (write code)
    ↓
pocketpal-tester        (write and run tests)
    ↓
pocketpal-reviewer      (quality gate)
    ↓
[DRAFT PR]
    ↓
[HUMAN REVIEW & MERGE]
```

## Available Agents

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| `pocketpal-orchestrator` | Entry point, task analysis | Start any new task |
| `pocketpal-planner` | Create implementation plans | After orchestrator, before coding |
| `pocketpal-implementer` | Write code | After plan approval |
| `pocketpal-tester` | Write and run tests | After implementation |
| `pocketpal-reviewer` | Quality checks | Before PR creation |

## Linked Codebases

- **PocketPal**: `/Users/aghorbani/codes/pocketpal-ai`
- **Advisory System**: `/Users/aghorbani/codes/sparing-partner-agents`

## Critical Files

### For Testing (READ THESE)
PocketPal has specific testing patterns. Agents MUST understand:
- `pocketpal-ai/jest/setup.ts` - Global mocks
- `pocketpal-ai/jest/test-utils.tsx` - Custom render with providers
- `context/patterns.md` - Patterns including testing mistakes to avoid

### For Context
- `context/pocketpal-overview.md` - Codebase structure
- `context/patterns.md` - MobX, components, testing patterns

## Current Phase

**Phase 1: Foundation** - Single-agent sequential workflow

### Parallel Execution (Phase 2)

For running multiple agents on different features simultaneously:

```bash
# Create worktrees for each feature (from pocketpal-ai repo)
cd /Users/aghorbani/codes/pocketpal-ai
git worktree add ../pocketpal-dev-team/worktrees/feature-123 -b feature/issue-123
git worktree add ../pocketpal-dev-team/worktrees/feature-456 -b feature/issue-456

# Run agents (from pocketpal-dev-team)
cd /Users/aghorbani/codes/pocketpal-dev-team
claude "Use pocketpal-orchestrator for issue #123 in worktrees/feature-123/"
# In another terminal:
claude "Use pocketpal-orchestrator for issue #456 in worktrees/feature-456/"
```

Each agent works in its own worktree = no conflicts.

### Upcoming Phases
- Phase 2: Parallel execution (git worktrees, 2-3 agents)
- Phase 3: Specialized agents (frontend, backend, etc.)
- Phase 4: Scale (10+ agents, learning, metrics)

## Key Design Decisions

1. **Claude Code Native** - Built on Claude Code's agent system
2. **Story Files** - Self-contained context per task (BMAD-inspired)
3. **Centralized Mocking** - Tests use PocketPal's existing infrastructure
4. **Human Gates** - Plan approval + PR review required
5. **Pattern Compliance** - Agents must follow existing codebase patterns
