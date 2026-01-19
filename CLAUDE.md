# PocketPal Dev Team

AI-powered autonomous development team for PocketPal AI.

## Overview

This project contains the agent definitions, workflows, and orchestration logic for an AI development team that can:
- Take GitHub issues or Linear tickets
- Research the codebase and create implementation plans
- Implement features/fixes with proper tests
- Open draft PRs for human review
- Scale to 10-20 parallel agents working on different features

## Project Structure

```
pocketpal-dev-team/
├── agents/              # Agent definitions (.md files)
│   ├── orchestrator.md  # Entry point, task routing
│   ├── planner.md       # Codebase research, plan creation
│   ├── implementer.md   # Code writing
│   ├── tester.md        # Test writing and execution
│   └── reviewer.md      # Code review, quality gates
├── workflows/           # YAML workflow definitions
├── context/             # Shared context for PocketPal
│   ├── architecture.md  # Codebase architecture summary
│   ├── patterns.md      # Coding patterns to follow
│   └── standards.md     # Coding standards
├── templates/           # Story file and PR templates
├── orchestrator/        # Orchestration scripts
└── docs/                # Documentation
    └── research/        # Research and analysis
```

## Quick Start

### Phase 1: Single Agent Workflow

```bash
# From pocketpal-ai repo, run orchestrator with an issue
claude --agent orchestrator "Implement GitHub issue #123"
```

### Phase 2: Parallel Execution (Coming Soon)

```bash
# Assign multiple issues
./orchestrator/assign-issues.sh 123 456 789
```

## Agent Invocation

Agents are invoked via Claude Code's Task tool with custom definitions:

```
subagent_type: "pocketpal-planner"
prompt: "Create implementation plan for: [issue description]"
```

## Linked Codebases

- **PocketPal**: `/Users/aghorbani/codes/pocketpal-ai`
- **Advisory System**: `/Users/aghorbani/codes/sparing-partner-agents`

## Current Phase

**Phase 1: Foundation** - Building single-agent workflow

## Key Design Decisions

1. **Claude Code Native** - Built on Claude Code's Task/agent system
2. **Story Files** - Self-contained context for each task (BMAD-inspired)
3. **Git Worktrees** - Parallel isolation without conflicts
4. **Human Gates** - Plan approval + PR review
