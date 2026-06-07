# PocketPal Dev Team

Starter Claude Code setup for [PocketPal AI](https://github.com/a-ghorbani/pocketpal-ai) development. Includes agents, workflows, and templates - extend as needed.

## How It Works

A four-stage pipeline — **Intent → WHAT → HOW → Implementation** — followed by an
independent review loop and a human merge gate.

```text
  Issue / description
         │
         ▼
  ┌──────────────┐  builds a self-contained intent-brief.md, classifies complexity
  │   intake     │  (trivial / quick / standard / complex), and stops with
  └──────┬───────┘  NEEDS_INPUT if required answers are missing
         │
         │   complexity decides which design stages run:
         │     • trivial          → straight to implementer
         │     • quick            → planner only
         │     • standard/complex → architect + planner
         ▼
  ┌──────────────┐  revise   ┌───────────────────┐   WHAT (standard/complex): explore 2–3
  │  architect   │ ◄───────► │ architect-critic  │   design candidates, then distill one
  └──────┬───────┘  max 2    └───────────────────┘   what.md  (exploration required for complex)
         ▼          rounds
  ┌──────────────┐  revise   ┌───────────────────┐   HOW (quick/standard/complex): explore 2–3
  │   planner    │ ◄───────► │   plan-critic     │   plan candidates, then distill one
  └──────┬───────┘  max 2    └───────────────────┘   how.md  (exploration required for complex)
         ▼          rounds
  ┌──────────────┐  code + commits + architecture-doc update
  │ implementer  │
  └──────┬───────┘
         ▼
  ┌──────────────┐  tests + coverage
  │   tester     │
  └──────┬───────┘
         ▼
  ┌──────────────┐  opens a DRAFT PR  (REQUEST_CHANGES → back to implementer)
  │  pipeline-   │
  │  reviewer    │
  └──────┬───────┘
         ▼
  ┌──────────────┐  /review-pr → workflows/reviews/PR-<n>/round-<N>/final.md
  │ independent  │  BLOCKER / CONCERN findings → PR-fix loop → back to implementer
  │   review     │  (max 2 external rounds, then escalate)
  └──────┬───────┘
         ▼
   HUMAN REVIEW & MERGE
```

**Key Points:**

- All work happens in **isolated git worktrees** — never touches the main branch directly
- **Explore-then-distill**: for complex work (and risky standard work), the architect and planner first sketch 2–3 candidate designs/plans, then synthesize a single `what.md`/`how.md`; critics review only the distilled result
- The pipeline keeps **WHAT (design) and HOW (plan) separate**, each gated by its own critic loop (max 2 rounds, then escalate)
- **Independent review** stays separate from the implementation agents; a human only steps in when the loops can't converge or a reviewer escalates
- **Human checkpoint**: PR review before merge
- **Headless-safe invocation**: every agent call is self-contained; missing information returns `NEEDS_INPUT`
- Each agent **verifies its environment** (worktree, branch, story context) before starting work

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

If you plan to run iOS/Android builds, copy your env and config files to the submodule. The worktree tooling will automatically copy these (via the allowlisted sync) into each worktree:

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

### 4. Start a Task

```bash
/start-task #123             # Start from a GitHub issue
/start-task "Add feature X"  # Start from a description
```

`/start-task` is the top-level delivery controller: it creates the worktree, runs the pipeline through a draft PR, then drives the independent review and any review-fix rounds.

When another agent or control plane drives this workflow, pass a self-contained brief in the prompt. Do not pass internal tracker IDs and expect the dev team to look them up. If required information is missing, intake stops with `NEEDS_INPUT:` instead of guessing.

## Safety Guarantees

The dev team has **built-in safeguards** to prevent common mistakes:

| Protection | How It Works |
| --- | --- |
| **Worktree Isolation** | All work happens in `worktrees/TASK-xxx/`, never in `pocketpal-ai` directly |
| **Branch Protection** | Agents refuse to work on `main`/`master` - only feature branches |
| **Native Build Verification** | For native changes, agents MUST run `pod install` and actual builds |
| **Pre-Flight Checks** | Every agent verifies environment before starting work |

## Workflow

Each stage produces a durable artifact and hands off to the next:

| Stage | Agent | Output |
| --- | --- | --- |
| Intent | `pocketpal-intake` | `workflows/stories/<TASK-ID>/intent-brief.md` (or `NEEDS_INPUT` stop) |
| WHAT | `pocketpal-architect` | `what.md` (delta on `context/architecture/<flow>.md`) |
| WHAT review | `pocketpal-architect-critic` | LGTM / HAS_CONCERNS / HAS_BLOCKERS |
| HOW | `pocketpal-planner` | `how.md` |
| HOW review | `pocketpal-plan-critic` | LGTM / HAS_CONCERNS / HAS_BLOCKERS / ARCHITECTURE_DRIFT |
| Implementation | `pocketpal-implementer` | code + commits + architecture-doc update |
| Test | `pocketpal-tester` | tests + coverage |
| Final review | `pocketpal-pipeline-reviewer` | draft PR or REQUEST_CHANGES |
| Independent review | `/review-pr` + role reviewers | `workflows/reviews/<TARGET-ID>/round-<N>/final.md` |

Before drafting the final WHAT/HOW, the architect and planner can run a **lightweight exploration pass** — `design-candidate-{A,B,C}.md` / `plan-candidate-{A,B,C}.md` (the third only when a materially different option exists) — then distill exactly one contract artifact. Exploration is **required for complex** tasks and **optional for risky standard** tasks (competing architecture shapes, migrations, native/security changes, tricky sequencing). Critics review only the synthesized `what.md`/`how.md`, not the candidates.

Complexity, picked by intake, decides which stages run:

| Level | When | Pipeline applied |
| --- | --- | --- |
| **trivial** | Single-file copy / config / typo / version bump (< 20 lines, no new contract) | Intent → Implementer |
| **quick** | 1–3 files, no contract change, existing flow doc covers the area | Intent → Planner → Plan-critic → Implementer |
| **standard** | Touches a contract (data model, persistence, wire format, rendering), multi-file | Full pipeline |
| **complex** | Cross-flow, new flow, architecture-changing | Full pipeline (both critic loops expected to use the full budget) |

See [`AGENTS.md`](./AGENTS.md) for the full pipeline contract, critic-loop semantics, and non-negotiables.

## Example Tasks

```bash
# Feature
/start-task "Add haptic feedback when sending messages"

# Bug fix
/start-task "Fix crash when loading large models on low-memory devices"

# From a GitHub issue
/start-task #123

# Self-contained brief (native - will run pod install + builds)
/start-task "Upgrade llama.rn from 0.12.0 to 0.12.1 to pick up the upstream structured-output fix. Keep the change limited to the dependency bump and required lockfile/native refresh. Verify with typecheck, the structured-output regression path, pod install, and iOS/Android native builds."
```

## Agents

**Pipeline agents** (run in order by `/start-task`):

| Agent | Purpose |
| --- | --- |
| `pocketpal-intake` | Entry point — builds the intent brief, classifies complexity, routes downstream |
| `pocketpal-architect` | Produces `what.md` — the WHAT (design delta on the architecture library) |
| `pocketpal-architect-critic` | Reviews `what.md` for design gaps; triggers revision if needed |
| `pocketpal-planner` | Produces `how.md` — the HOW (step-by-step implementation plan) |
| `pocketpal-plan-critic` | Reviews `how.md`; flags `ARCHITECTURE_DRIFT` back to the architect |
| `pocketpal-implementer` | Writes code IN WORKTREE, runs platform builds for native changes |
| `pocketpal-tester` | Writes and runs tests IN WORKTREE using PocketPal's testing patterns |
| `pocketpal-pipeline-reviewer` | Quality gate — verifies builds + tests, opens the draft PR |

**Review & support agents:**

| Agent | Purpose |
| --- | --- |
| `pocketpal-code-reviewer` | Independent review of a branch or PR (`/review-pr`), separate from the pipeline |
| Role reviewers | `architect-reviewer`, `qa-reviewer`, `security-reviewer`, `performance-reviewer`, `mobile-reviewer`, `data-reviewer`, `ux-reviewer`, `local-invariants-reviewer`, `design-parity-reviewer` — dimension-specific review lenses |
| `pocketpal-proposer` / `pocketpal-challenger` | Propose / challenge technical solutions (used in `/deliberate`) |

## Native Changes

When a task involves native dependencies (llama.rn, react-native-\*, etc.):

1. Intake flags `NATIVE_CHANGES: YES`
2. Implementer runs `pod install` and verifies iOS/Android builds
3. The pipeline reviewer **independently verifies** builds succeed before opening the PR

The dev team will NOT claim "build ready" without actually running builds.

## Invoke Agents Directly

Normally you run the whole thing with `/start-task`. To drive a single stage yourself, pass the worktree, branch, and story context in the prompt:

```bash
# Just create a plan (no implementation)
claude "Use pocketpal-planner to create how.md for: Add dark mode support
WORKTREE: ./worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200"

# Implement an existing story
claude "Use pocketpal-implementer to implement story TASK-20250115-1200
WORKTREE: ./worktrees/TASK-20250115-1200
BRANCH: feature/TASK-20250115-1200
STORY: ./workflows/stories/TASK-20250115-1200/"

# Review a branch or PR independently
/review-pr 490
```

**Note**: When invoking pipeline agents directly (not through `/start-task`), you MUST provide the WORKTREE and BRANCH parameters. Agents will refuse to work without them.

## Parallel Development

Since each task runs in its own git worktree, you can safely run multiple workstreams in parallel from the same directory. No need to clone the repo multiple times or set up separate folders - just open separate terminals:

```bash
# Terminal 1
/start-task "Add feature A"

# Terminal 2
/start-task "Fix bug B"

# Terminal 3
/start-task "Refactor component C"
```

Each task automatically creates an isolated worktree:

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
claude --dangerously-skip-permissions "/start-task <task>"
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
├── context/
│   ├── architecture/     # Cumulative architecture library (one doc per flow)
│   └── patterns.md       # Coding & testing patterns
├── workflows/
│   ├── stories/          # Per-task artifacts (intent-brief / what / how)
│   └── reviews/          # Independent review output (final.md per round)
├── worktrees/            # Git worktrees for isolated development
├── templates/            # Artifact templates (intent / what / how / review)
├── tools/                # Utility scripts (create/remove-worktree.sh, etc.)
└── AGENTS.md             # The full pipeline contract & non-negotiables
```

## Key Files

- `context/patterns.md` - Coding patterns (especially testing - read this!)
- `workflows/stories/` - Story files created by planner
- `.claude/settings.json` - Auto-approved commands

## Tips

1. **Be specific** — More detail in your task = better results
2. **Check the PR** — The critic loops handle WHAT/HOW review; focus your attention on the final PR
3. **Check tests** — PocketPal has specific testing patterns (centralized mocks)
4. **Trust the guards** — Agents will refuse to work in wrong environments
5. **Native = slow** — Tasks with native changes take longer (builds required)

## When Reviews Find Issues

During PR review, you may find problems with the implementation:

| Issue Size | Action |
| --- | --- |
| **Minor** (typos, small tweaks) | Ask the agent to fix directly |
| **Significant** (wrong approach, missing requirements) | Update the story file, discard the PR, and re-run the workflow |

**Why?** The story file is the source of truth. For significant issues, patching the code leads to drift between the plan and implementation. It's cleaner to:

1. Update the story with the correct approach
2. Close/discard the current PR (or `git reset` to before implementation)
3. Re-run from implementer with the updated story

This keeps the story accurate and ensures the implementation follows a proper plan.

## Cleanup

After a task is merged, clean up the worktree with the allowlisted tool (never raw `git worktree remove` or `rm -r`):

```bash
./tools/remove-worktree.sh TASK-xxx --yes
```

## Optional Features

| Feature | Requirement | Without It |
| --- | --- | --- |
| Native iOS builds | Xcode + CocoaPods | Set `NATIVE_CHANGES=NO` or skip native tasks |
| Native Android builds | Android SDK + Gradle | Set `NATIVE_CHANGES=NO` or skip native tasks |

## Requirements

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- Git 2.20+ (for worktree support)
- Node.js 18+ (for PocketPal development)
- (Optional) Xcode 15+ for iOS builds
- (Optional) Android SDK for Android builds
