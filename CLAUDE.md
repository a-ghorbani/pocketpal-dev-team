# PocketPal Dev Team

AI-powered autonomous development team for PocketPal AI.

## Overview

This project contains the agent definitions, workflows, and orchestration logic for an AI development team that can:
- Take GitHub issues or Linear tickets
- Research the codebase and create implementation plans
- Implement features/fixes with proper tests
- Open draft PRs for human review
- Scale to 10-20 parallel agents working on different features (Phase 2+)

## Safety Guarantees (Built-In)

Every agent has **hard stops** that prevent critical mistakes:

| Protection | Enforcement |
|------------|-------------|
| **Worktree Isolation** | Pre-flight check: `pwd` must contain `worktrees/TASK-` |
| **Branch Protection** | Pre-flight check: branch must NOT be `main` or `master` |
| **Native Build Verification** | `NATIVE_CHANGES=YES` triggers mandatory `pod install` + builds |
| **Context Passing** | Agents refuse to work without `WORKTREE` and `BRANCH` params |

If any pre-flight check fails, agents STOP and report the error.

## Project Structure

```
pocketpal-dev-team/
├── .claude/
│   └── agents/              # Claude Code custom agent definitions
│       ├── pocketpal-orchestrator.md  # Creates worktree, routes tasks
│       ├── pocketpal-planner.md       # Creates implementation plans
│       ├── pocketpal-implementer.md   # Writes code, runs builds
│       ├── pocketpal-tester.md        # Writes tests
│       └── pocketpal-reviewer.md      # Quality gate, creates PR
├── context/                 # Shared context for PocketPal
│   ├── pocketpal-overview.md
│   └── patterns.md          # Coding & testing patterns (CRITICAL)
├── workflows/
│   └── stories/             # Story files (implementation plans)
├── templates/
│   └── story-template.md    # Template for new stories
├── worktrees/               # Git worktrees for parallel development
│   └── README.md            # Instructions for creating worktrees
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
claude "Use pocketpal-planner to create a story for: [description]
WORKTREE: /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-xxx
BRANCH: feature/TASK-xxx"
```

### Workflow

```
Issue/Prompt
    ↓
pocketpal-orchestrator  (create worktree, classify, route)
    ↓
pocketpal-planner       (research IN WORKTREE, create story)
    ↓
[HUMAN APPROVAL]        (review and approve plan)
    ↓
pocketpal-implementer   (write code IN WORKTREE, run builds if native)
    ↓
pocketpal-tester        (write/run tests IN WORKTREE)
    ↓
pocketpal-reviewer      (verify builds, quality gate)
    ↓
[DRAFT PR from feature branch]
    ↓
[HUMAN REVIEW & MERGE]
```

## Available Agents

| Agent | Purpose | Key Safety Checks |
|-------|---------|-------------------|
| `pocketpal-orchestrator` | Entry point, creates worktree | Creates isolated environment |
| `pocketpal-planner` | Create implementation plans | Verifies worktree + branch |
| `pocketpal-implementer` | Write code, run builds | Verifies worktree + branch, runs native builds |
| `pocketpal-tester` | Write and run tests | Verifies worktree + branch |
| `pocketpal-reviewer` | Quality checks, PR creation | Verifies worktree + branch, runs native builds |

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

**Phase 1: Foundation** - Single-agent sequential workflow with safety guarantees

### Parallel Execution (Phase 2)

For running multiple agents on different features simultaneously:

```bash
# Start multiple tasks in separate terminals
cd /Users/aghorbani/codes/pocketpal-dev-team

# Terminal 1
claude "Use pocketpal-orchestrator: Add feature A"

# Terminal 2
claude "Use pocketpal-orchestrator: Fix bug B"
```

Each agent automatically creates its own worktree = no conflicts.

### Upcoming Phases
- Phase 2: Parallel execution (2-3 agents simultaneously)
- Phase 3: Specialized agents (frontend, backend, etc.)
- Phase 4: Scale (10+ agents, learning, metrics)

## Key Design Decisions

1. **Claude Code Native** - Built on Claude Code's agent system
2. **Story Files** - Self-contained context per task (BMAD-inspired)
3. **Centralized Mocking** - Tests use PocketPal's existing infrastructure
4. **Human Gates** - Plan approval + PR review required
5. **Pattern Compliance** - Agents must follow existing codebase patterns
6. **Worktree Isolation** - All work in worktrees, never in main repo
7. **Branch Protection** - Agents refuse to work on main/master
8. **Native Build Verification** - Agents MUST run actual builds for native changes
