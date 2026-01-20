# PocketPal Dev Team

AI-powered autonomous development team for PocketPal AI. Takes issues/tasks and delivers implementations with tests.

## Quick Start

```bash
cd /Users/aghorbani/codes/pocketpal-dev-team

# Start a task
claude "Use pocketpal-orchestrator: <your task description>"
```

## Safety Guarantees

The dev team has **built-in safeguards** to prevent common mistakes:

| Protection | How It Works |
|------------|--------------|
| **Worktree Isolation** | All work happens in `worktrees/TASK-xxx/`, never in `pocketpal-ai` directly |
| **Branch Protection** | Agents refuse to work on `main`/`master` - only feature branches |
| **Native Build Verification** | For native changes, agents MUST run `pod install` and actual builds |
| **Pre-Flight Checks** | Every agent verifies environment before starting work |

## Workflow

```
Your Task
    ↓
pocketpal-orchestrator    → Creates worktree, analyzes task, classifies
    ↓
pocketpal-planner         → Researches IN WORKTREE, creates plan
    ↓
[YOU APPROVE PLAN]        → Review the story file
    ↓
pocketpal-implementer     → Writes code IN WORKTREE, runs builds if native
    ↓
pocketpal-tester          → Writes and runs tests IN WORKTREE
    ↓
pocketpal-reviewer        → Quality checks, platform builds if native
    ↓
[DRAFT PR from feature branch]
```

## Example Tasks

```bash
# Feature
claude "Use pocketpal-orchestrator: Add haptic feedback when sending messages"

# Bug fix
claude "Use pocketpal-orchestrator: Fix crash when loading large models on low-memory devices"

# Dependency upgrade (native - will run pod install + builds)
claude "Use pocketpal-orchestrator: Upgrade llama.rn to latest version"

# From GitHub issue
claude "Use pocketpal-orchestrator: Implement GitHub issue #123"
```

## Agents

| Agent | Purpose |
|-------|---------|
| `pocketpal-orchestrator` | Entry point - creates worktree, analyzes tasks, routes to other agents |
| `pocketpal-planner` | Researches codebase IN WORKTREE, creates detailed implementation plans |
| `pocketpal-implementer` | Writes code IN WORKTREE, runs platform builds for native changes |
| `pocketpal-tester` | Writes and runs tests IN WORKTREE using PocketPal's testing patterns |
| `pocketpal-reviewer` | Quality gate - verifies builds, code quality, creates PR |

## Native Changes

When a task involves native dependencies (llama.rn, react-native-*, etc.):

1. Orchestrator flags `NATIVE_CHANGES: YES`
2. Implementer runs `pod install` and verifies iOS/Android builds
3. Reviewer **independently verifies** builds succeed before approval

The dev team will NOT claim "build ready" without actually running builds.

## Invoke Agents Directly

```bash
# Just create a plan (no implementation)
claude "Use pocketpal-planner to create a story for: Add dark mode support
WORKTREE: /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200"

# Implement an existing story
claude "Use pocketpal-implementer to implement story TASK-20250115-1200
WORKTREE: /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200
STORY: /Users/aghorbani/codes/pocketpal-dev-team/workflows/stories/TASK-20250115-1200.md"

# Review before PR
claude "Use pocketpal-reviewer to review TASK-20250115-1200
WORKTREE: /Users/aghorbani/codes/pocketpal-dev-team/worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200"
```

**Note**: When invoking agents directly (not through orchestrator), you MUST provide the WORKTREE and BRANCH parameters. Agents will refuse to work without them.

## Parallel Development

Run multiple features simultaneously - each gets its own worktree:

```bash
# Start multiple tasks in separate terminals
cd /Users/aghorbani/codes/pocketpal-dev-team

# Terminal 1
claude "Use pocketpal-orchestrator: Add feature A"

# Terminal 2
claude "Use pocketpal-orchestrator: Fix bug B"

# Each creates its own worktree:
# worktrees/TASK-20250115-1430/
# worktrees/TASK-20250115-1431/
```

No conflicts because each agent works in isolated worktrees.

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
│   ├── agents/           # Agent definitions with pre-flight checks
│   └── settings.json     # Permission rules
├── context/              # Codebase patterns & overview
├── workflows/stories/    # Implementation plans (story files)
├── worktrees/            # Git worktrees for isolated development
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
4. **Trust the guards** - Agents will refuse to work in wrong environments
5. **Native = slow** - Tasks with native changes take longer (builds required)

## Cleanup

After a task is merged, clean up the worktree:

```bash
cd /Users/aghorbani/codes/pocketpal-ai
git worktree remove ../pocketpal-dev-team/worktrees/TASK-xxx
```
