# PocketPal Dev Team

An agentic dev team for [PocketPal AI](https://github.com/a-ghorbani/pocketpal-ai), runnable under Claude Code, Codex, opencode, or pi. It takes an issue or a description to a reviewed draft PR; a human reviews and merges.

## How it works

A four-stage pipeline — **Intent → WHAT → HOW → Implementation** — followed by an independent review loop and a human merge gate.

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
  ┌──────────────┐  revise   ┌───────────────────┐
  │  architect   │ ◄───────► │ architect-critic  │   what.md — design delta on
  └──────┬───────┘  max 2    └───────────────────┘   context/architecture/<flow>.md
         ▼          rounds
  ┌──────────────┐  revise   ┌───────────────────┐
  │   planner    │ ◄───────► │   plan-critic     │   how.md — step-by-step plan
  └──────┬───────┘  max 2    └───────────────────┘
         ▼          rounds
  ┌──────────────┐  code + commits + architecture-doc update
  │ implementer  │
  └──────┬───────┘
         ▼
  ┌──────────────┐  tests + coverage + visual captures
  │   tester     │
  └──────┬───────┘
         ▼
  ┌──────────────┐  opens a DRAFT PR  (REQUEST_CHANGES → back to implementer)
  │  pipeline-   │
  │  reviewer    │
  └──────┬───────┘
         ▼
  ┌──────────────┐  /review-pr → role reviewers → final verdict
  │ independent  │  BLOCKER / CONCERN findings → PR-fix loop
  │   review     │  (max 2 rounds, then escalate)
  └──────┬───────┘
         ▼
   HUMAN REVIEW & MERGE
```

The full runbook (stage outputs, complexity matrix, critic loops, stop conditions) is [`docs/workflows/pipeline.md`](docs/workflows/pipeline.md). The rules every agent obeys are in [`AGENTS.md`](AGENTS.md).

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
| Instructions | `CLAUDE.md` → `AGENTS.md` | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
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
├── skills/               # skills: start-task, review-pr, run-e2e, bench, ... (source of truth)
├── context/
│   ├── architecture/     # per-flow architecture truth (indexed in its README)
│   └── patterns.md       # coding and testing patterns
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
