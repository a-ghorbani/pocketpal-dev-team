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

### System-Level Protections (Hooks & Permissions)

Additional protections enforced by Claude Code settings (`.claude/settings.json`):

| Protection | Mechanism |
|------------|-----------|
| **Block commits to main** | Hook: `tools/block-commit-to-main.sh` blocks `git commit` on main/master |
| **Submodule read-only** | Hook: `tools/guard-submodule-edit.sh` blocks Edit/Write to `repos/pocketpal-ai/` |
| **Submodule git guard** | Hook: `tools/guard-submodule-git.sh` blocks mutating git commands in `repos/pocketpal-ai/` |
| **Path-scoped edits** | Permission: Edit/Write denied for `repos/pocketpal-ai/**`, allowed in `worktrees/**` |
| **Block force push** | Permission: Denies `git push -f` and `git push origin main` |
| **Secrets protection** | Permission: Denies Read/Edit of `.env` files |

> **Why is `repos/pocketpal-ai/` read-only?** Multiple agents run in parallel and all
> create worktrees from this submodule. Any direct modification (file edits, branch
> switches, commits) would corrupt the shared reference and break all other agents.

### Submodule is READ-ONLY — No Exceptions

`repos/pocketpal-ai/` is **only for reading source code and creating worktrees**. Agents must NEVER:

- **Reference submodule build artifacts** (e.g., `repos/pocketpal-ai/ios/build/...` as `E2E_APP_PATH`)
- **Run builds, tests, or E2E specs** from/against the submodule
- **Use submodule paths in env vars** pointing to outputs (builds, screenshots, reports)
- **Upload or commit submodule files** as assets

**If a worktree needs a build, build it IN the worktree.** Never borrow artifacts from `repos/pocketpal-ai/`.

## Project Structure

```
pocketpal-dev-team/
├── .claude/
│   └── agents/              # Claude Code custom agent definitions
│       ├── pocketpal-orchestrator.md  # Creates worktree, routes tasks
│       ├── pocketpal-planner.md       # Creates implementation plans
│       ├── pocketpal-story-critic.md  # Reviews plans for design gaps
│       ├── pocketpal-implementer.md   # Writes code, runs builds
│       ├── pocketpal-tester.md        # Writes tests
│       └── pocketpal-reviewer.md      # Quality gate, creates PR
├── context/                 # Shared context for PocketPal
│   ├── pocketpal-overview.md
│   └── patterns.md          # Coding & testing patterns (CRITICAL)
├── workflows/
│   └── stories/             # Story files (implementation plans)
├── templates/
│   ├── story-template.md         # Standard story template (features, bugs)
│   └── quick-story-template.md   # Quick story template (typos, config)
├── worktrees/               # Git worktrees for parallel development
│   └── README.md            # Instructions for creating worktrees
└── docs/
    └── research/            # Research and analysis
```

## Quick Start

### Slash Commands (Recommended)

```bash
# Review an external PR
/review-pr 490

# Start from a GitHub issue
/start-task #123

# Start from a description
/start-task "Add dark mode toggle to settings"

# Start from an action-tracker item
/start-action "lifecycle guard"
```

### Manual Invocation (Alternative)

```bash
# Analyze and implement a GitHub issue
claude "Use pocketpal-orchestrator to analyze GitHub issue #123"

# Start with a description
claude "Use pocketpal-orchestrator: Add dark mode toggle to settings"

# Create a plan only
claude "Use pocketpal-planner to create a story for: [description]
WORKTREE: ./worktrees/TASK-xxx
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
pocketpal-story-critic  (review plan for design gaps — skipped for quick tasks)
    ↓
[HUMAN APPROVAL]        (review story + critique, approve plan)
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
| `pocketpal-story-critic` | Review plans for design gaps | Verifies story + worktree exist |
| `pocketpal-implementer` | Write code, run builds | Verifies worktree + branch, runs native builds |
| `pocketpal-tester` | Write and run tests | Verifies worktree + branch |
| `pocketpal-reviewer` | Quality checks, PR creation | Verifies worktree + branch, runs native builds |

## Linked Codebases

- **PocketPal**: `./repos/pocketpal-ai` (git submodule)
- **Linear Integration**: `./tools/linear.sh` (requires `LINEAR_API_KEY` in `.env`)

## Critical Files

### For Testing (READ THESE)
PocketPal has specific testing patterns. Agents MUST understand:
- `repos/pocketpal-ai/jest/setup.ts` - Global mocks
- `repos/pocketpal-ai/jest/test-utils.tsx` - Custom render with providers
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
cd .

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

## Worktree Management

**CRITICAL**: Worktree commands must be run from `repos/pocketpal-ai` (the submodule), NOT from pocketpal-dev-team root.

```bash
# Create worktree (from repos/pocketpal-ai)
cd repos/pocketpal-ai
git worktree add ../../worktrees/TASK-xxx -b feature/TASK-xxx

# Remove worktree (from repos/pocketpal-ai)
cd repos/pocketpal-ai
git worktree remove ../../worktrees/TASK-xxx
```

See `worktrees/README.md` for full documentation.

## Naming Conventions

**Consistent naming across the entire workflow:**

| Type | Worktree | Branch | Story File |
|------|----------|--------|------------|
| New Task | `worktrees/TASK-YYYYMMDD-HHMM` | `feature/TASK-YYYYMMDD-HHMM` | `TASK-YYYYMMDD-HHMM.md` |
| PR Fix | `worktrees/PR-{number}` | `pr-{number}` | `PR-{number}-fix.md` |

**Examples:**
- `TASK-20250120-1430` for new features/bugs
- `PR-490` / `PR-490-fix.md` for PR review fixes

---

## CRITICAL RULE: Story Files Required

**ALL implementation work requires a story file, including:**
- New features (standard story)
- Bug fixes (standard or quick story)
- PR review fixes (standard story)
- Dependency upgrades (standard story)
- Quick fixes like typos (quick story)

### Quick vs Standard Stories

| Complexity | Template | Use When |
|------------|----------|----------|
| **quick** | `templates/quick-story-template.md` | Typo, config, single-file, <30 lines |
| **standard** | `templates/story-template.md` | Features, bugs, 2+ files |

**The workflow is ALWAYS:**
```
Task/Issue/PR Fix
    ↓
Orchestrator (creates worktree, classifies complexity)
    ↓
Planner (creates story file - quick or standard)
    ↓
Story Critic (reviews plan for design gaps — skipped for quick tasks)
    ↓
[HUMAN APPROVAL]
    ↓
Implementation
```

**Agents must NEVER:**
- Enter "plan mode" and start implementing
- Write code without a story file
- Skip human approval
- Create plans outside of story files
- Route quick tasks directly to implementer (they still need a quick story)

---

## GitHub Conventions

**Signature** - Include at the end of all GitHub content (PRs, issues, comments):
```
🤖 Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team)
```

**Git commits** - NEVER add `Co-Authored-By` trailers. This is enforced by hook.
PocketPal Dev Team does not use individual AI model attribution in commits.

**Title formats** (per repo issue templates):
| Type | Title Format | Label |
|------|--------------|-------|
| Bug | `[Bug]: <description>` | `bug` |
| Feature | `[Feat]: <description>` | `enhancement` |
| PR | Short description (<70 chars) | - |
