# PocketPal Dev Team

Starter Claude Code setup for [PocketPal AI](https://github.com/a-ghorbani/pocketpal-ai) development. Includes agents, workflows, and templates - extend as needed.

## How It Works

<p align="center">
  <img src="assets/pipeline.svg" alt="PocketPal Dev Team Pipeline" width="700">
</p>

**Key Points:**
- All work happens in **isolated git worktrees** — never touches main branch directly
- Two **human checkpoints** (amber): plan approval before coding, PR review before merge
- Each agent **verifies its environment** before starting work
- Supports **light and dark mode** automatically

## Getting Started

### 1. Clone with Submodules

```bash
git clone --recursive https://github.com/a-ghorbani/pocketpal-dev-team.git
cd pocketpal-dev-team
```

If you already cloned without `--recursive`:
```bash
git submodule update --init --recursive
```

### 2. (Optional) Use Your Own Fork

If you want to work with your own fork of pocketpal-ai:

```bash
cd repos/pocketpal-ai
git remote add myfork git@github.com:YOUR_USERNAME/pocketpal-ai.git
git fetch myfork
```

### 3. (Optional) Set Up Secrets for Native Builds

If you plan to run iOS/Android builds, copy your env and config files to the submodule. The orchestrator will automatically copy these to each worktree:

```bash
# Copy your secrets to repos/pocketpal-ai/
cp /path/to/your/.env repos/pocketpal-ai/
cp /path/to/your/e2e/.env repos/pocketpal-ai/e2e/

# iOS
cp /path/to/your/ios/.xcode.env.local repos/pocketpal-ai/ios/
cp /path/to/your/ios/GoogleService-Info.plist repos/pocketpal-ai/ios/
cp /path/to/your/ios/Config/Env.xcconfig repos/pocketpal-ai/ios/Config/

# Android
cp /path/to/your/android/local.properties repos/pocketpal-ai/android/
cp /path/to/your/android/app/google-services.json repos/pocketpal-ai/android/app/
```

These files are gitignored by pocketpal-ai, so they won't be committed.

### 4. (Optional) Configure Linear Integration

For the `/start-action` skill to work with Linear:

```bash
cp .env.example .env
# Edit .env and add your LINEAR_API_KEY
```

### 5. Start a Task

```bash
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
WORKTREE: ./worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200"

# Implement an existing story
claude "Use pocketpal-implementer to implement story TASK-20250115-1200
WORKTREE: ./worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200
STORY: ./workflows/stories/TASK-20250115-1200.md"

# Review before PR
claude "Use pocketpal-reviewer to review TASK-20250115-1200
WORKTREE: ./worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200"
```

**Note**: When invoking agents directly (not through orchestrator), you MUST provide the WORKTREE and BRANCH parameters. Agents will refuse to work without them.

## Parallel Development

Since each task runs in its own git worktree, you can safely run multiple workstreams in parallel from the same directory. No need to clone the repo multiple times or set up separate folders - just open separate terminals:

```bash
# Terminal 1
claude "Use pocketpal-orchestrator: Add feature A"

# Terminal 2
claude "Use pocketpal-orchestrator: Fix bug B"

# Terminal 3
claude "Use pocketpal-orchestrator: Refactor component C"
```

Each orchestrator automatically creates an isolated worktree:
```
worktrees/
├── TASK-20250115-1430/   # Feature A
├── TASK-20250115-1431/   # Bug B
└── TASK-20250115-1432/   # Refactor C
```

No conflicts, no setup overhead - worktrees handle the isolation.

## Autonomous Mode

Skip permission prompts for faster execution:

```bash
claude --dangerously-skip-permissions "Use pocketpal-orchestrator: <task>"
```

Safe commands are pre-allowed in `.claude/settings.json`. Dangerous commands (rm -rf, curl, .env access) are blocked.

## Project Structure

```
pocketpal-dev-team/
├── repos/
│   └── pocketpal-ai/     # Git submodule - the target codebase
├── .claude/
│   ├── agents/           # Agent definitions with pre-flight checks
│   ├── skills/           # Slash command skills (/start-task, /review-pr, etc.)
│   └── settings.json     # Permission rules
├── context/              # Codebase patterns & overview
├── workflows/stories/    # Implementation plans (story files)
├── worktrees/            # Git worktrees for isolated development
├── templates/            # Story file templates
└── tools/                # Utility scripts (linear.sh, etc.)
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

## When Reviews Find Issues

During PR review, you may find problems with the implementation:

| Issue Size | Action |
|------------|--------|
| **Minor** (typos, small tweaks) | Ask the agent to fix directly |
| **Significant** (wrong approach, missing requirements) | Update the story file, discard the PR, and re-run the workflow |

**Why?** The story file is the source of truth. For significant issues, patching the code leads to drift between the plan and implementation. It's cleaner to:

1. Update the story with the correct approach
2. Close/discard the current PR (or `git reset` to before implementation)
3. Re-run from implementer with the updated story

This keeps the story accurate and ensures the implementation follows a proper plan.

## Cleanup

After a task is merged, clean up the worktree:

```bash
cd repos/pocketpal-ai
git worktree remove ../../worktrees/TASK-xxx
```

## Optional Features

| Feature | Requirement | Without It |
|---------|-------------|------------|
| `/start-action` skill | `LINEAR_API_KEY` in `.env` | Use `/start-task` instead |
| Native iOS builds | Xcode + CocoaPods | Set `NATIVE_CHANGES=NO` or skip native tasks |
| Native Android builds | Android SDK + Gradle | Set `NATIVE_CHANGES=NO` or skip native tasks |

## Requirements

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Git 2.20+ (for worktree support)
- Node.js 18+ (for PocketPal development)
- (Optional) Xcode 15+ for iOS builds
- (Optional) Android SDK for Android builds
