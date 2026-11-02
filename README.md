# PocketPal Dev Team

An agentic dev team for [PocketPal AI](https://github.com/a-ghorbani/pocketpal-ai), runnable under Claude Code, Codex, opencode, or pi. It takes an issue or a description to a reviewed draft PR; a human reviews and merges.

## How it works

Intent → WHAT → Implementation, then an independent review loop and a human merge gate. Design premises are proven by running something, evidence is planned before any code, and a wrong design goes back to the architect.

```text
  Issue / description
         │
         ▼
  ┌──────────────┐  intent-brief.md, evidence.md (claim, platforms, risk rows),
  │   intake     │  decisions.md (product calls with defaults), context.md (lessons
  └──────┬───────┘  and past work that apply); classifies by riskiest contract;
         │          NEEDS_INPUT only for an unclear request or a slicing proposal
         │
         │     • bug              → tester reproduces on main, finds the cause
         │                          (git history for regressions)
         │     • open product calls or complex work → researcher: user need
         │       (issues, feedback, reviews, forums) and how others solve it
         │     then by size:
         │     • trivial / quick  → implementer
         │     • standard/complex → architect (complex: a design arena first, where
         │                          Codex and Claude lanes design independently,
         │                          a judge scores them, the architect merges)
         ▼
  ┌──────────────┐  revise   ┌───────────────────┐   what.md: delta on context/architecture/<flow>.md,
  │  architect   │ ◄───────► │ architect-critic  │   premises proven by spikes
  └──────┬───────┘  max 2    └───────────────────┘
         │
         │  (planner ⇄ plan-critic only when sequencing is a risk: multi-PR, migration, staged native)
         ▼
  ┌──────────────┐  tracer slice ─► architect-reviewer ─► finish; flow-doc update.
  │ implementer  │  A false premise → DESIGN_INVALIDATED → architect
  └──────┬───────┘
         ▼
  ┌──────────────┐  a receipt per evidence.md row: mutation-checked tests,
  │   tester     │  device / store / server / capture runs
  └──────┬───────┘
         ▼
  ┌──────────────┐  receipts + simplicity check → DRAFT PR + evidence comment
  │  pipeline-   │
  │  reviewer    │
  └──────┬───────┘
         ▼  tools/pr-gates.sh (CI green, evidence posted)
  ┌──────────────┐  /review-pr → role reviewers → refutation (real? worth it?) → verdict
  │ independent  │  findings → fix brief → plan-critic → fix → re-verify
  │   review     │  (2 rounds total, then escalate)
  └──────┬───────┘
         ▼
   HUMAN REVIEW & MERGE ─► finalization: remove worktrees, distill the task's lessons
```

The full runbook (complexity, routing, evidence, decisions, restarts, stop conditions) is [`docs/workflows/pipeline.md`](docs/workflows/pipeline.md). The rules every agent obeys are in [`AGENTS.md`](AGENTS.md).

## Lessons

What agents learn (device quirks, harness traps, operator rulings) lives in `context-private/lessons/`, one fact per file. It is local only: gitignored here, versioned by its own local git, never published. Intake gathers the lessons that apply to a task, finalization writes new ones, and anyone can query them:

```bash
tools/context search <terms>   # lessons, past stories, reviews, flow docs
tools/context index            # every lesson, one line each
tools/context sync             # lint, regenerate the index, commit locally
```

## Getting started

### 1. Clone with submodules

```bash
git clone --recursive https://github.com/a-ghorbani/pocketpal-dev-team.git
cd pocketpal-dev-team
```

If you already cloned without `--recursive`: `git submodule update --init --recursive`.

To work against your own fork, add it as a remote inside `repos/pocketpal-ai` (`git remote add myfork …`, `git fetch myfork`).

### 2. (Optional) Secrets for native builds

For iOS/Android builds, place your env and config files in the submodule. The worktree tooling copies them into each task worktree through an allowlisted sync:

```bash
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

These files are gitignored by pocketpal-ai.

### 3. Start a task

From the repo root, in any supported harness:

```text
/start-task #123                                   # GitHub issue
/start-task "Add haptic feedback when sending"     # free-form description
/review-pr 490                                     # independent review of a PR
```

In Codex, skills are invoked as `$start-task …`. When another agent drives the team, pass a self-contained brief; missing information stops intake with `NEEDS_INPUT:` rather than a guess.

Each task gets its own git worktree under `worktrees/`, so several tasks can run in parallel from separate terminals.

## Harnesses

| | Claude Code | Codex | opencode | pi |
| --- | --- | --- | --- | --- |
| Instructions | `AGENTS.md` (v2.1.277+) | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
| Roles | `.claude/agents/` (symlinks) | `.codex/agents/*.toml` (stubs) | `.opencode/agents/` (symlinks) | `.pi/agents/` (symlinks; needs pi's subagent extension) |
| Skills | `.claude/skills/` (symlinks) | `.agents/skills/` (symlinks) | both | `.agents/skills/` |
| Guards | hooks in `.claude/settings.json` | `.codex/hooks.json` + `.codex/rules/` | `.opencode/plugins/guards.ts` | `.pi/extensions/guards/` |
| Permissions | allow all, deny list | sandbox profile in `.codex/config.toml` | `opencode.json` | no sandbox; guards only |
| Unattended | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` | allowed by default | `--approve` or trusted project |

pi has no MCP support. Its subagent tool is pi's own MIT example extension, vendored under `.pi/extensions/subagent/` (see its `VENDORED.md`), which reads the `.pi/agents/` links; dispatch needs `agentScope: "project"`.

All four point at one source: roles in `agents/`, skills in `skills/`. See "Harness layout" in `AGENTS.md`. Codex needs the project trusted and its hooks approved once via `/hooks`.

## Safety

| Protection | How |
| --- | --- |
| Worktree isolation | All app work happens in `worktrees/<TASK>/`; the `repos/pocketpal-ai` submodule is read-only (hook-enforced) |
| Branch protection | No commits or pushes to `main`/`master` from task work; no force-push |
| Secrets | Agents never read `.env`, keystores, or key files; config reaches worktrees only via `tools/sync-worktree-config.sh` |
| Native verification | Native changes require `pod install` + iOS and Android builds before a PR is called ready |
| Visual evidence | UI changes carry captures posted to the PR |

## Cleanup

After a task merges, remove its worktree with the allowlisted tool (never raw `git worktree remove` or `rm -r`):

```bash
./tools/remove-worktree.sh TASK-xxx --yes
```

## Layout

```text
pocketpal-dev-team/
├── repos/pocketpal-ai/   # git submodule — the app (read-only)
├── agents/               # role definitions (source of truth)
├── config/               # design-arena lanes: harness, model, effort
├── skills/               # skills: start-task, review-pr, run-e2e, bench, ... (source of truth)
├── context/
│   ├── architecture/     # per-flow architecture truth (indexed in its README)
│   └── patterns.md       # coding and testing patterns
├── context-private/      # lessons learned (local only, gitignored)
├── docs/                 # pipeline runbook, standards, workflows
├── templates/            # intent / what / how / review templates
├── tools/                # worktree, guard, GitHub, device, and tracker scripts
├── workflows/            # per-task stories and reviews (local, gitignored)
├── worktrees/            # task worktrees (local, gitignored)
└── AGENTS.md             # rules every agent obeys
```

## Requirements

- One agent harness: [Claude Code](https://code.claude.com), [Codex CLI](https://github.com/openai/codex), [opencode](https://opencode.ai), or [pi](https://pi.dev)
- Git 2.20+, Node.js 18+, `jq`, Python 3.11+
- Optional: Xcode 15+ and CocoaPods (iOS builds), Android SDK (Android builds)
- Optional, for the design arena: `tmux`, both Claude Code and Codex CLI, and agistry (`config/design-arena.conf`)
