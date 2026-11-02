# Agent Instructions

Workflow control plane for PocketPal AI. The app is the read-only submodule `repos/pocketpal-ai`; app work happens in worktrees made from it. Delivery runbook: [`docs/workflows/pipeline.md`](docs/workflows/pipeline.md).

## Guardrails

For every agent and task; mostly hook-enforced.

- **Submodule read-only.** Inside `repos/pocketpal-ai/`, never edit, build, test, commit, switch branches, use its build artifacts, or upload its files as generated assets. Read it by absolute path (`git -C "$ROOT/repos/pocketpal-ai" …`; relative paths break after `cd`).
- **Worktrees.**
  - App work happens in `worktrees/<TASK-or-PR>/` on a non-`main` branch, created only from the submodule by `tools/create-worktree.sh`. Remove them only with `./tools/remove-worktree.sh <name> --yes`: at finalization after merge (no extra permission), otherwise only when the user asks. Never raw `git worktree remove`/`prune`, `rm -r`, or `rmdir`.
  - Exception: a worktree in the ios-router or design-arena ledger may be removed by the tool or worker that created it once that work is done (`skills/ios-router`, `tools/design-arena.sh`).
  - Stop and report when inside the submodule, on `main`/`master`, or missing the `WORKTREE`, `BRANCH`, or story context your task needs.
- **Secrets.** Never read `.env`, `.env.*`, keystores, or key files (hook-guarded). Config reaches worktrees only through `tools/sync-worktree-config.sh` / `tools/create-worktree.sh`; never bulk-copy it.
- **App code reaches `main` only through a reviewed PR.** Push the feature branch; never push, fast-forward, or merge onto the app's `main` yourself (hook-enforced, any refspec).
- **Public artifacts.** GitHub artifacts (PRs, comments, issues, commit messages) and app source, tests, and configs reference only public things (`#123`, file paths, library names), never internal tracker IDs (`context/issue-tracking.md`), `linear.app` links, task IDs, or story anchors (`I_DSn`, `Dn`, `§4x`, `Scenario X`, `WHAT/HOW`, `round N`).

## Lessons

Lessons live in `context-private/`: local only; never commit, publish, or quote them in public text.

- **Read.** A handoff block's `CONTEXT` first. Outside the pipeline, `tools/context search <terms>` before work on a device, e2e, native, build, or release surface.
- **Write.** What a future task would otherwise rediscover (a trap, false premise, tool quirk, general operator ruling): update the covering lesson or add one, then `tools/context sync`. One fact per file in `context-private/lessons/`, frontmatter `name` (the file name), `description`, `type`; a rule has **Why:** and **How to apply:** lines. Skip what git, code, or a flow doc holds.

## Delivery rules

For work that becomes an app PR.

- **Never review your own work:** implementation and independent review are separate roles. The orchestrator never prompts between stages; its stops are in `pipeline.md`.
- **Story gate.** Every task has `intent-brief.md`, `evidence.md`, `decisions.md`; standard and complex add `what.md`; `PLAN=YES` adds `how.md`.
- **Facts are proven, product calls are the operator's.** A design premise is read from code or proven by a spike. User-visible behaviour the request leaves open, or accepting a regression, is a product call logged with a recommended default, never decided by an agent.
- **Asking the operator.** A question only the human can answer goes to `agistry.sh send operator` (Slack), never only into chat: one message, every open question with its recommended default; the reply comes to your `task:role`. Log each answer in `decisions.md` as a ruling. Only top-level sessions send (the `/start-task` orchestrator, the PM); stage roles reply `NEEDS_INPUT`.
- **A wrong design goes back.** A stage that finds a premise false or a decision wrong replies `DESIGN_INVALIDATED` instead of patching around it (`docs/workflows/design-and-restarts.md`, Going back).
- **Architecture docs** (`context/architecture/`, one per flow; lifecycle in its README). Changing behaviour a flow doc describes updates it in the same round (path-scoped commit here, not in the app PR). A line for code not yet on `main` carries `(pending #<PR>)` (`(pending <TASK_ID>)` before the PR exists). For standard and complex work, WHAT is a detailed delta on the flow doc that the implementer distills into it. The architect runs a drift check first; drift is a bug.
- **Native changes.** Touching `package.json`, native modules, `ios/`, `android/`, a Podfile, or `build.gradle` is `NATIVE_CHANGES=YES`: ready only after `pod install`, an iOS build, and an Android build.
- **Evidence.** Intake plans in `evidence.md` what a change must show, CI-APK device runs included (`docs/workflows/evidence-and-decisions.md`, Evidence plan); every row closes with a receipt. A PR changing visible UI carries durable captures (`docs/workflows/visual-capture.md`).
- **Comments.** Default to none. A comment usually flags a redundant line (delete it), unclear code (fix it), or a forced design (rationale goes to `context/architecture/`). Keep only a genuine "why" the code can't show (test: `docs/standards/code-review.md`, Comments).

## Shared checkout

One checkout on `main`, shared by parallel sessions (`worktrees/` belong to the *app* repo).

- **Architecture docs** (last writer wins silently): before editing `context/architecture/`, run `git status --porcelain -- context/architecture/`; a foreign modification means stop; commit your change at once, path-scoped (`git commit -- <file>`, never `add -A`).
- **Story files.** `workflows/stories/*` and `workflows/reviews/*` exist only on the writing machine; inline their content in a PR, never cite the path.
- **Follow-ups.** An agent can only arm a mechanism that outlives it; "I'll do X when the build finishes", then exiting, arms nothing.
- **Review subagents.** The user authorises the delegated subreviews (`pocketpal-reviewer`, prompted per lens) wherever the review workflow requires them.

## Harness layout

One source for Claude Code, Codex, opencode, and pi.

- Roles in `agents/<name>.md`, skills in `skills/<name>/SKILL.md` are the only copies; edit them directly. `tools/sync-harness.py` points harness paths at them (symlinks for `.claude/`, `.opencode/`, `.pi/` agents and all skill dirs; one-line stubs in `.codex/agents/*.toml`). Run it only to add, rename, or remove a role or skill, or change a role's description; `--check` reports drift.
- Guards (`tools/guard-*.sh`) are hooks in `.claude/settings.json`, `.codex/hooks.json`, `.opencode/plugins/guards.ts`, and `.pi/extensions/guards/`. Add a new guard to all four.
- Source files use plain paths ("Read `docs/...`"), never `@path` imports; only Claude expands those.

## GitHub conventions

Signature: one line naming the harness, the only footer (no injected footers or session links).

```text
Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team) · <Claude Code | Codex | opencode | pi>
```

- **Bot identity.** Every public GitHub write (`pr create`, `pr comment`, `issue comment`, `pr review --comment` / `--request-changes`) goes through `tools/ghb` (`gh` as the `pocketpal-dev-team[bot]` App). Approvals and merges stay on the operator's account; `ghb` refuses them. Without the bot token it runs as the operator and warns; if it can't run, plain `gh` is fine. Setup: `docs/workflows/github-bot-identity.md`.
- **Commits and titles.** No `Co-Authored-By` trailers (hook-enforced). Titles: `[Bug]: …` (label `bug`), `[Feat]: …` (label `enhancement`), or a short PR description under 70 characters.
- **Brevity.** GitHub and tracker text is short and factual: what changed and what it fixes, never reasoning, process narrative, or restated diffs. PR body: the app's `.github/PULL_REQUEST_TEMPLATE.md`, a few-line description, the signature. Commits: one subject line; a body only for a fact the subject can't carry. PR comments, review replies, tracker comments: a few lines, pointing to the commit, file, or capture.

## Worktrees and naming

| Type | Worktree | Branch | Story directory |
| --- | --- | --- | --- |
| New task | `worktrees/TASK-YYYYMMDD-HHMM` | `feature/TASK-YYYYMMDD-HHMM` | `workflows/stories/TASK-YYYYMMDD-HHMM/` |
| PR fix | `worktrees/PR-<n>` | `pr-<n>` | `workflows/stories/PR-<n>-fix/` |
| PR E2E | `worktrees/PR-<n>-e2e` | detached | n/a |

```bash
./tools/create-worktree.sh TASK-YYYYMMDD-HHMM   # branch feature/TASK-..., ref origin/main
./tools/create-worktree.sh PR-490 --branch pr-490 --ref refs/remotes/pr/490   # after fetching +pull/490/head:refs/remotes/pr/490
./tools/create-worktree.sh PR-490-e2e --detach --ref origin/<branch>
./tools/sync-worktree-config.sh ./worktrees/<name>   # re-sync allowlisted config
./tools/remove-worktree.sh <name> --yes [--force]    # at finalization after merge, or when the user asks
```

## Key references

`templates/`; `context/architecture/README.md`; `context/patterns.md`, `context/pocketpal-overview.md`; `docs/standards/code-review.md`, `docs/workflows/visual-capture.md`; tracker routing `context/issue-tracking.md`.
