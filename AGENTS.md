# Agent Instructions

This repo is the workflow control plane for PocketPal AI. The app lives in the read-only submodule `repos/pocketpal-ai`; all app work happens in worktrees created from it. The delivery runbook (pipeline, handoff block, routing, complexity, critic loops) is [`docs/workflows/pipeline.md`](docs/workflows/pipeline.md).

## Guardrails

These hold for every agent and every task. Most are hook-enforced.

- **Submodule read-only.** Inside `repos/pocketpal-ai/`, never edit, build, test, commit, or switch branches, and never use its build artifacts or upload its files as generated assets. Read it with absolute paths (`git -C "$ROOT/repos/pocketpal-ai" …`, `grep -rn … "$ROOT/repos/pocketpal-ai/src"`); after a `cd`, the harness can't resolve relative paths.
- **Worktrees.**
  - App work happens in `worktrees/<TASK-or-PR>/` on a non-`main` branch.
  - Create worktrees only from the submodule, via `tools/create-worktree.sh`.
  - Remove them only with `./tools/remove-worktree.sh <name> --yes`, and only when the user asks. Never use raw `git worktree remove`/`prune`, `rm -r`, or `rmdir`.
  - Stop and report when you're inside the submodule, on `main`/`master`, or missing the `WORKTREE`, `BRANCH`, or story context your task needs.
- **Secrets.** Agents never read `.env`, `.env.*`, keystores, or key files (hook-guarded). Config reaches worktrees only through `tools/sync-worktree-config.sh` / `tools/create-worktree.sh`; never bulk-copy it.
- **Public artifacts.** GitHub artifacts (PR title, body, and comments; issues; commit messages) and everything in the app (source, tests, configs) reference only public things: GitHub `#123`, file paths, library names. Leave out:
  - internal tracker IDs (`context/issue-tracking.md`) and `linear.app` links;
  - task IDs;
  - story anchors (`I_DSn`, `Dn`, `§4x`, `Scenario X`, `WHAT/HOW`, `round N`).

## Delivery rules

These apply to work that becomes an app PR.

- **Keep the four stages intact:** Intent → WHAT → HOW → Implementation. Implementation and independent review never collapse into one role. The orchestrator runs stages without interactive prompts; the stop conditions are in `pipeline.md`.
- **Story gate.** Trivial work needs `intent-brief.md`; quick work adds `how.md`; standard and complex work add `what.md`.
- **Architecture docs** (`context/architecture/`, one per flow; lifecycle in its README):
  - a PR that changes behaviour a flow doc describes updates that doc in the same PR;
  - for standard and complex work, WHAT is a delta on the flow doc, and the implementer absorbs it;
  - the architect runs a drift check first, because drift is a bug.
- **Native changes.** Work touching `package.json`, native modules, `ios/`, `android/`, a Podfile, or `build.gradle` is `NATIVE_CHANGES=YES`. It needs `pod install`, an iOS build, and an Android build before it is ready.
- **Visual evidence.** A PR that changes visible UI carries durable captures posted to the PR (`docs/workflows/visual-capture.md`).
- **Comments.** Default to none. A comment is usually a symptom:
  - of a redundant line: delete it;
  - of unclear code: fix the code;
  - of a forced design: move the rationale to `context/architecture/`.

  Keep only a genuine "why" the code cannot show. The full test is under "Comments" in `docs/standards/code-review.md`.

## Shared checkout

This repo is one checkout on `main`, shared by parallel sessions (`worktrees/` belong to the *app* repo).

- **Architecture docs.** A lost update here is silent (last writer wins, and the diff looks clean). So:
  - before editing `context/architecture/`, run `git status --porcelain -- context/architecture/`;
  - a foreign modification means stop;
  - commit your change at once, path-scoped (`git commit -- <file>`, never `add -A`).
- **Story files.** `workflows/stories/*` and `workflows/reviews/*` exist only on the machine that wrote them. Put their content inline in a PR instead of citing the path.
- **Follow-ups.** An agent can only arm a mechanism that outlives it. "I will do X when the build finishes", followed by exiting, arms nothing.
- **Review subagents.** The user authorises delegated subreviews (architect, QA, security, performance, mobile, data, UX, local-invariants) wherever the review workflow requires them.

## Harness layout

This repo runs under Claude Code, Codex, and opencode from one source:

- Roles live in `agents/<name>.md` and skills in `skills/<name>/SKILL.md`. These are the only copies, so edit them directly.
- Harness paths point back at them:
  - `.claude/` and `.opencode/` agents, and all skill dirs, are symlinks;
  - `.codex/agents/*.toml` are one-line stubs.

  `tools/sync-harness.py` creates them. Run it only when you add, rename, or remove a role or skill, or change a role's description; `--check` reports drift.
- The guards are the `tools/guard-*.sh` scripts, wired as hooks in `.claude/settings.json`, `.codex/hooks.json`, and `.opencode/plugins/guards.ts`. Add a new guard to all three.
- Source files use plain paths ("Read `docs/...`"), never `@path` imports; only Claude expands those.

## GitHub conventions

Signature: one line naming the harness that did the work. It is the only footer, with no harness-injected footers and no session links.

```text
Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team) · <Claude Code | Codex | opencode>
```

**Bot identity.** Every public GitHub write goes through `tools/ghb`, which runs `gh` as the `pocketpal-dev-team[bot]` App. That covers `pr create`, `pr comment`, `issue comment`, and `pr review --comment` / `--request-changes`.
- Approvals and merges stay on the operator's account; `ghb` refuses them.
- When the bot token is unavailable, `ghb` runs as the operator and warns. If `ghb` can't run, plain `gh` is fine.
- Setup: `docs/workflows/github-bot-identity.md`.

**Commits and titles.**
- Commits never carry `Co-Authored-By` trailers (hook-enforced).
- Titles: `[Bug]: …` (label `bug`), `[Feat]: …` (label `enhancement`), or a short PR description under 70 characters.

## Worktrees and naming

| Type | Worktree | Branch | Story directory |
| --- | --- | --- | --- |
| New task | `worktrees/TASK-YYYYMMDD-HHMM` | `feature/TASK-YYYYMMDD-HHMM` | `workflows/stories/TASK-YYYYMMDD-HHMM/` |
| PR fix | `worktrees/PR-<n>` | `pr-<n>` | `workflows/stories/PR-<n>-fix/` |
| PR E2E | `worktrees/PR-<n>-e2e` | detached | n/a |

```bash
./tools/create-worktree.sh TASK-YYYYMMDD-HHMM                       # branch feature/TASK-..., ref origin/main
./tools/create-worktree.sh PR-490 --branch pr-490 --ref pr-490      # fetch the PR ref first
./tools/create-worktree.sh PR-490-e2e --detach --ref origin/<branch>
./tools/sync-worktree-config.sh ./worktrees/<name>                  # re-sync allowlisted config
./tools/remove-worktree.sh <name> --yes [--force]                   # only when the user asks
```

## Key references

- Pipeline runbook: `docs/workflows/pipeline.md`
- Templates: `templates/`
- Architecture library: `context/architecture/README.md`
- Project context: `context/patterns.md`, `context/pocketpal-overview.md`
- Standards: `docs/standards/code-review.md`, `docs/workflows/visual-capture.md`
- Tracker routing: `context/issue-tracking.md`
