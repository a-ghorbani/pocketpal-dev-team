# Agent Instructions

This repo is the workflow control plane for PocketPal AI. The app lives in the read-only submodule `repos/pocketpal-ai`; all app work happens in worktrees created from it. The delivery runbook (handoff block, routing, evidence, decisions, restarts) is [`docs/workflows/pipeline.md`](docs/workflows/pipeline.md).

## Guardrails

These hold for every agent and task; most are hook-enforced.

- **Submodule read-only.** Inside `repos/pocketpal-ai/`, never edit, build, test, commit, or switch branches, and never use its build artifacts or upload its files as generated assets. Read it with absolute paths (`git -C "$ROOT/repos/pocketpal-ai" …`, `grep -rn … "$ROOT/repos/pocketpal-ai/src"`); after a `cd`, the harness can't resolve relative paths.
- **Worktrees.**
  - App work happens in `worktrees/<TASK-or-PR>/` on a non-`main` branch.
  - Create worktrees only from the submodule, via `tools/create-worktree.sh`.
  - Remove them only with `./tools/remove-worktree.sh <name> --yes`. Removing a task's worktrees is part of finalization once its PR is merged (no extra permission needed); otherwise only when the user asks. Never use raw `git worktree remove`/`prune`, `rm -r`, or `rmdir`.
  - Exception: a worktree in the ios-router or design-arena ledger was created at an agent's request, not the user's; the tool or worker that created it may remove it once that work is finished (`skills/ios-router`, `tools/design-arena.sh`).
  - Stop and report when you're inside the submodule, on `main`/`master`, or missing the `WORKTREE`, `BRANCH`, or story context your task needs.
- **Secrets.** Agents never read `.env`, `.env.*`, keystores, or key files (hook-guarded). Config reaches worktrees only through `tools/sync-worktree-config.sh` / `tools/create-worktree.sh`; never bulk-copy it.
- **App code reaches `main` only through a reviewed PR.** Push the feature branch; never push, fast-forward, or merge a branch onto the app's `main` yourself (hook-enforced, any refspec).
- **Public artifacts.** GitHub artifacts (PR title, body, and comments; issues; commit messages) and everything in the app (source, tests, configs) reference only public things: GitHub `#123`, file paths, library names. Leave out:
  - internal tracker IDs (`context/issue-tracking.md`) and `linear.app` links;
  - task IDs;
  - story anchors (`I_DSn`, `Dn`, `§4x`, `Scenario X`, `WHAT/HOW`, `round N`).

## Lessons

Lessons learned live in `context-private/`: local only, never committed here, published, or quoted in public text.

- **Read.** When the handoff block has `CONTEXT`, read it first. Outside the pipeline, run `tools/context search <terms>` before working on a device, e2e, native, build, or release surface.
- **Write.** When you learn something a future task would otherwise rediscover (a trap, a false premise, a tool quirk, an operator ruling of general scope), update the lesson that covers it or add one, then run `tools/context sync`.
  - One fact per file in `context-private/lessons/`, with frontmatter `name` (the file name), `description`, and `type`.
  - A rule carries **Why:** and **How to apply:** lines.
  - Leave out what git, the code, or a flow doc already holds.

## Delivery rules

These apply to work that becomes an app PR.

- **Never review your own work:** implementation and independent review stay separate roles. The orchestrator never prompts between stages; its stops are in `pipeline.md`.
- **Story gate.** Every task has `intent-brief.md`, `evidence.md`, and `decisions.md`; standard and complex work add `what.md`; `PLAN=YES` adds `how.md`.
- **Facts are proven, product calls are the operator's.** A design premise is read from code or proven by a spike. User-visible behaviour the request leaves open, or accepting a regression, is logged as a product call with a recommended default, never decided by an agent.
- **Asking the operator.** A question only the human can answer goes to `agistry.sh send operator` (it reaches them on Slack), never only into chat output. Send one message with every open question, each with its recommended default; the reply comes back to your `task:role`. Log each answer in `decisions.md` as a ruling. Only top-level sessions send (the `/start-task` orchestrator, the PM); stage roles reply `NEEDS_INPUT`.
- **A wrong design goes back.** A stage that finds a premise false or a decision wrong replies `DESIGN_INVALIDATED` instead of patching around it (`pipeline.md`, Going back).
- **Architecture docs** (`context/architecture/`, one per flow; lifecycle in its README):
  - a change to behaviour a flow doc describes updates that doc in the same round. that update is a path-scoped commit in this repo, not part of the app PR;
  - a line describing code not yet on `main` carries `(pending #<PR>)` (`(pending <TASK_ID>)` until the PR exists);
  - for standard and complex work, WHAT is a detailed delta on the flow doc, and the implementer distills it into the doc;
  - the architect runs a drift check first; drift is a bug.
- **Native changes.** Work touching `package.json`, native modules, `ios/`, `android/`, a Podfile, or `build.gradle` is `NATIVE_CHANGES=YES`. It needs `pod install`, an iOS build, and an Android build before it is ready.
- **Evidence.** Intake plans what a change must show in `evidence.md`, including CI-APK device runs (risk table: `pipeline.md`, Evidence plan); every row closes with a receipt. A PR that changes visible UI carries durable captures (`docs/workflows/visual-capture.md`).
- **Comments.** Default to none. A comment is usually a symptom:
  - of a redundant line: delete it;
  - of unclear code: fix the code;
  - of a forced design: move the rationale to `context/architecture/`.

  Keep only a genuine "why" the code cannot show. The full test is under "Comments" in `docs/standards/code-review.md`.

## Shared checkout

This repo is one checkout on `main`, shared by parallel sessions (`worktrees/` belong to the *app* repo).

- **Architecture docs** (last writer wins silently):
  - before editing `context/architecture/`, run `git status --porcelain -- context/architecture/`;
  - a foreign modification means stop;
  - commit your change at once, path-scoped (`git commit -- <file>`, never `add -A`).
- **Story files.** `workflows/stories/*` and `workflows/reviews/*` exist only on the machine that wrote them. Put their content inline in a PR instead of citing the path.
- **Follow-ups.** An agent can only arm a mechanism that outlives it. "I will do X when the build finishes", followed by exiting, arms nothing.
- **Review subagents.** The user authorises delegated subreviews (architect, QA, security, performance, mobile, data, UX, local-invariants, and the code-reviewer when no role subreviews are needed) and the review-map helpers (review-map-architect, flow-analyst, requirements-mapper) wherever the review workflow requires them.

## Harness layout

This repo runs under Claude Code, Codex, opencode, and pi from one source:

- Roles live in `agents/<name>.md` and skills in `skills/<name>/SKILL.md`. These are the only copies, so edit them directly.
- Harness paths point back at them:
  - `.claude/`, `.opencode/` and `.pi/` agents, and all skill dirs, are symlinks;
  - `.codex/agents/*.toml` are one-line stubs.

  `tools/sync-harness.py` creates them. Run it only when you add, rename, or remove a role or skill, or change a role's description; `--check` reports drift.
- The guards are the `tools/guard-*.sh` scripts, wired as hooks in `.claude/settings.json`, `.codex/hooks.json`, `.opencode/plugins/guards.ts`, and `.pi/extensions/guards/`. Add a new guard to all four.
- Source files use plain paths ("Read `docs/...`"), never `@path` imports; only Claude expands those.

## GitHub conventions

Signature: one line naming the harness that did the work. It is the only footer, with no harness-injected footers and no session links.

```text
Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team) · <Claude Code | Codex | opencode | pi>
```

**Bot identity.** Every public GitHub write goes through `tools/ghb`, which runs `gh` as the `pocketpal-dev-team[bot]` App. That covers `pr create`, `pr comment`, `issue comment`, and `pr review --comment` / `--request-changes`.
- Approvals and merges stay on the operator's account; `ghb` refuses them.
- When the bot token is unavailable, `ghb` runs as the operator and warns. If `ghb` can't run, plain `gh` is fine.
- Setup: `docs/workflows/github-bot-identity.md`.

**Commits and titles.**
- Commits never carry `Co-Authored-By` trailers (hook-enforced).
- Titles: `[Bug]: …` (label `bug`), `[Feat]: …` (label `enhancement`), or a short PR description under 70 characters.

**Brevity.** Everything written to GitHub or a tracker is short and factual: what changed and what it fixes, never reasoning, process narrative, or restated diffs.
- PR body: the app's `.github/PULL_REQUEST_TEMPLATE.md`, with a description of a few lines, then the signature.
- Commits: one subject line; a body only when the subject cannot carry a needed fact.
- PR comments, review replies, and tracker comments: a few lines at most, pointing to the commit, file, or capture rather than retelling it.

## Worktrees and naming

| Type | Worktree | Branch | Story directory |
| --- | --- | --- | --- |
| New task | `worktrees/TASK-YYYYMMDD-HHMM` | `feature/TASK-YYYYMMDD-HHMM` | `workflows/stories/TASK-YYYYMMDD-HHMM/` |
| PR fix | `worktrees/PR-<n>` | `pr-<n>` | `workflows/stories/PR-<n>-fix/` |
| PR E2E | `worktrees/PR-<n>-e2e` | detached | n/a |

```bash
./tools/create-worktree.sh TASK-YYYYMMDD-HHMM                       # branch feature/TASK-..., ref origin/main
./tools/create-worktree.sh PR-490 --branch pr-490 --ref refs/remotes/pr/490   # after fetching +pull/490/head:refs/remotes/pr/490
./tools/create-worktree.sh PR-490-e2e --detach --ref origin/<branch>
./tools/sync-worktree-config.sh ./worktrees/<name>                  # re-sync allowlisted config
./tools/remove-worktree.sh <name> --yes [--force]                   # at finalization after merge, or when the user asks
```

## Key references

- Templates: `templates/`
- Architecture library: `context/architecture/README.md`
- Project context: `context/patterns.md`, `context/pocketpal-overview.md`
- Standards: `docs/standards/code-review.md`, `docs/workflows/visual-capture.md`
- Tracker routing: `context/issue-tracking.md`
