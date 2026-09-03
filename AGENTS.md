# Agent Instructions

This repo is the workflow control plane for PocketPal AI. The target app code is in `repos/pocketpal-ai`, but that submodule is read-only.

These are the always-on invariants every agent must obey, regardless of role. The orchestrator runbook — pipeline shape, stage handoffs, complexity matrix, critic loops, exploration policy — is in **[`docs/workflows/pipeline.md`](docs/workflows/pipeline.md)**.

## Non-Negotiables

- Never edit, build, commit, or switch branches inside `repos/pocketpal-ai/`. Use it only as the source repo for creating worktrees and reading source.
- All task work happens in `worktrees/<TASK-or-PR>/` on a non-`main` branch.
- Never create a worktree from the dev-team repo itself. Worktrees come from `repos/pocketpal-ai`.
- Never remove worktrees with raw `git worktree remove`, `git worktree prune`, `rm -r`, or `rmdir`. Use `./tools/remove-worktree.sh <name> --yes` only when the user explicitly asks for cleanup.
- Never bulk-copy secrets or config. Use only the allowlisted sync in `./tools/sync-worktree-config.sh` or `./tools/create-worktree.sh`.
- Never implement without the artefacts the complexity level requires (see Story gate).
- Keep the four-stage pipeline intact: **Intent → WHAT → HOW → Implementation** — implementation and independent review must never collapse into the same role. The orchestrator runs the pipeline autonomously (no interactive prompt between stages); the exact stop conditions are in `docs/workflows/pipeline.md`.
- `NATIVE_CHANGES=YES` requires `pod install` + iOS build + Android build before the work can be called ready.
- Every PR that changes behaviour described in `context/architecture/*.md` must update the relevant doc **in the same PR**. Drift is forbidden.
- Every PR that changes visible UI must carry durable visual evidence posted to the PR. The trigger, ownership, and posting mechanism are in **[`docs/workflows/visual-capture.md`](docs/workflows/visual-capture.md)**.
- **Issue tracking & routing:** see `context/issue-tracking.md` for how a work reference resolves to its tracker, and the internal-ID hygiene rule.
- **Public artifacts hygiene.** In GitHub artifacts (PR title/body/comment, issue, commit message) and in `repos/pocketpal-ai/` source/tests/configs, reference only public things — public GitHub issues/PRs, file paths, library names. No internal tracker IDs (see `context/issue-tracking.md`), no `linear.app`, no internal task IDs, no story-doc anchors (`I_DSn`, `Dn`, `§4x`, `Scenario X`, `WHAT/HOW`, `round N`). Source comments stay terse — current state, not the story.

## Operating Rules

### Worktree isolation

Every implementation, test, or PR review of PocketPal app code happens in a dedicated worktree under `worktrees/`. The submodule is only the source used to create worktrees and read source code.

Agents stop and report when:

- `pwd` is inside `repos/pocketpal-ai/`
- the current branch is `main` or `master`
- expected `WORKTREE`, `BRANCH`, or story context is missing
- a requested action would mutate, build, or commit inside the submodule

### Submodule read-only

`repos/pocketpal-ai/` is read-only. Agents must never edit, switch branches, commit, build, or test inside it; never reference its build artifacts; never upload its files as generated assets. Builds, tests, screenshots, and reports happen in a worktree.

Read it with absolute paths (`grep -rn … "$ROOT/repos/pocketpal-ai/src"`, `git -C "$ROOT/repos/pocketpal-ai" …`) rather than `cd repos/pocketpal-ai && grep … src`. The harness cannot resolve a relative path after `cd`, and when a `Read(...)` deny rule is in force that unresolved read becomes a permission prompt. Secret files (`.env`, `.env.*`, `*.keystore`) are guarded by `tools/guard-secrets-read.sh`, a hook rather than a deny rule, precisely so ordinary reads never prompt.

### Story gate

Implementation requires the artefacts the complexity level mandates. Trivial: `intent-brief.md`. Quick: + `how.md`. Standard / complex: + `what.md`.

### Architecture library

`context/architecture/` holds the cumulative architecture truth, one file per flow. See `context/architecture/README.md` for the lifecycle.

- Standard / complex stories produce `what.md` as a **delta** on the relevant flow doc.
- The implementer absorbs the approved delta into the flow doc in the **same PR** that lands the code (a step in `how.md`).
- Drift is treated as a bug. The architect runs a drift check at the start of every standard / complex story.

### Native verification

Tasks touching `package.json`, native modules, `ios/`, `android/`, Podfile, or build.gradle are `NATIVE_CHANGES=YES`. Required before "ready": `pod install`, an iOS build, an Android build. Missing native verification is a blocking review issue.

### Visual evidence

Tasks that change visible UI are `Visual Evidence Required=YES`. The pipeline must produce durable captures and post them to the PR before approval; "UI changed but no posted visual evidence" is a blocking review issue. Owners and the posting command are in `docs/workflows/visual-capture.md`.

### Comments: treat the urge to write one as a diagnostic

A comment is almost always a **symptom**, not a deliverable. Before writing one, work out which of these you are actually looking at — and fix *that*, rather than describing it:

1. **Bad comment** — it states what the code already says, narrates the change, or records how you arrived at the answer. → **Delete it.** Names and types already carry it.
2. **Bad code** — you need prose because the code is not self-explanatory. → **Fix the code.** Rename the variable, extract the function, drop the cleverness. The comment is buying silence for a readability problem.
3. **Bad design** — the comment justifies why something is done this odd way. → **Fix the design**, or if the oddity is genuinely forced, put the reasoning in `context/architecture/` where design rationale belongs, not above the call site.
4. **Genuine "why"** — a non-recoverable fact a future reader cannot derive from the code: an external constraint, non-obvious platform behaviour, a trap that looks like a bug and isn't. → **Keep it.** This is the rare case, not the normal one.

The test: *if I delete this line, what does a competent reader who knows the codebase but not this task actually lose?* If the answer is "nothing", it was case 1. If it is "they would misread the code", it is probably case 2 or 3 and the code should change. Only if the answer is "they would repeat a mistake the code cannot warn them about" is it case 4.

Two consequences worth stating explicitly, because they are where this usually goes wrong:

- **Volume is the signal.** A diff that needs many comments is reporting a design or clarity problem, not a documentation gap. Do not resolve it by writing better prose.
- **Nothing about the task belongs in source.** No "we hit X", no round numbers, no story anchors. Source describes the current state; the reasoning lives in the story and the architecture docs. (This overlaps Public artifacts hygiene above — same rule, different failure mode.)

Reviewers: flag over-commenting as a finding, and say **which of the four** it is. "Too many comments" is not actionable; "this is case 2, the function needs splitting" is.

### Secrets, config, cleanup

- Do not read, copy, or bulk-sync `.env` files or private config by hand. Use only the allowlisted sync tools.
- Do not remove worktrees outside `./tools/remove-worktree.sh <name> --yes`, and only when the user explicitly asks.

### Subagent authorisation for reviews

For PR reviews and high-risk code reviews, the user explicitly authorises delegated (e.g. Codex to use `spawn_agent`) subreviews (architect-reviewer, QA, security, performance, mobile, data, UX, local-invariants, etc.) as required by the review workflow.

## GitHub conventions

PR / issue / comment signature:

```text
Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team)
```

Bot identity: every public write on GitHub — `pr create`, `pr comment`, `issue comment`, `pr review --comment` / `--request-changes` — goes through `tools/ghb`, which runs `gh` as the `pocketpal-dev-team[bot]` GitHub App so readers see the author is automation. Approvals and merges stay on the operator's own account (`ghb` refuses them). Commits and pushes are unchanged. Getting the job done beats attribution: when the bot token is unavailable `ghb` runs the command as the operator and warns; if `ghb` itself is unusable, plain `gh` is fine. Setup: `docs/workflows/github-bot-identity.md`.

Commits: never add `Co-Authored-By` trailers (hook-enforced).

Titles: `[Bug]: ...` (label `bug`), `[Feat]: ...` (label `enhancement`), or a short PR description under 70 chars.

## Worktree commands

```bash
# New task
./tools/create-worktree.sh TASK-YYYYMMDD-HHMM
# Defaults: worktree=worktrees/TASK-..., branch=feature/TASK-..., ref=origin/main

# PR branch (fetch first)
./tools/create-worktree.sh PR-490 --branch pr-490 --ref pr-490

# Detached E2E from existing remote ref
./tools/create-worktree.sh PR-490-e2e --detach --ref origin/my-pr-branch

# Re-sync allowlisted config into an existing worktree
./tools/sync-worktree-config.sh ./worktrees/TASK-YYYYMMDD-HHMM

# Remove a worktree (only when the user explicitly asks)
./tools/remove-worktree.sh TASK-YYYYMMDD-HHMM --yes [--force]
```

## Naming and layout

| Type | Worktree | Branch | Story directory |
| --- | --- | --- | --- |
| New task | `worktrees/TASK-YYYYMMDD-HHMM` | `feature/TASK-YYYYMMDD-HHMM` | `workflows/stories/TASK-YYYYMMDD-HHMM/` |
| PR fix | `worktrees/PR-<n>` | `pr-<n>` | `workflows/stories/PR-<n>-fix/` |
| PR E2E | `worktrees/PR-<n>-e2e` | detached | n/a |

Inside a story directory:

```
intent-brief.md    # always
what.md            # standard / complex only
how.md             # quick / standard / complex (not trivial)
```

## Key references

- **Orchestrator runbook:** `docs/workflows/pipeline.md` (pipeline shape, stage handoffs, complexity matrix, critic loops, exploration policy)
- Templates: `templates/{intent,what,how}-template.md`, `templates/{design-candidate,plan-candidate,review-feedback}-template.md`
- Architecture library: `context/architecture/README.md`
- Project context: `context/patterns.md`, `context/pocketpal-overview.md`
- Standards: `docs/standards/code-review.md`, `docs/workflows/visual-capture.md`
