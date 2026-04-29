# Agent Instructions

This repo is the workflow control plane for PocketPal AI. The target app code
is in `repos/pocketpal-ai`, but that submodule is read-only.

## Non-Negotiables

- Never edit, build, commit, or switch branches inside `repos/pocketpal-ai/`.
  Use it only as the source repo for creating worktrees and reading source.
- All task work happens in `worktrees/<TASK-or-PR>/` on a non-`main` branch.
- Never create a worktree from the dev-team repo itself. Worktrees must come
  from `repos/pocketpal-ai`.
- Never remove or prune worktrees with raw `git worktree remove`,
  `git worktree prune`, `rm -r`, or `rmdir`. Use
  `./tools/remove-worktree.sh <name> --yes` only when the user explicitly asked
  for cleanup.
- Never bulk-copy secrets or config into a worktree. Only use the allowlisted
  sync in `./tools/sync-worktree-config.sh` or `./tools/create-worktree.sh`.
- Never implement without a story file in `workflows/stories/`.
- Keep the pipeline intact: orchestrate -> plan -> critique -> implement -> test
  -> review -> draft PR.
- If a task changes native dependencies or native code, treat it as
  `NATIVE_CHANGES=YES`: `pod install`, iOS build, and Android build are
  required before calling it ready.

## Workflow

All implementation work follows this pipeline:

```text
Issue/Prompt
    |
    v
pocketpal-orchestrator  (create worktree, classify, route)
    |
    v
pocketpal-planner       (research in worktree, create story v1)
    |
    v
pocketpal-story-critic  (blind review, structured critique)
    |
    +-- LGTM ------------------------------------------+
    |
    +-- HAS_CONCERNS / HAS_BLOCKERS                    |
        |                                             |
        v                                             |
    pocketpal-planner   (revision mode: address each  |
                         finding as FIXED/REJECTED/   |
                         DEFERRED, produce story v2)  |
        |                                             |
        v                                             |
    pocketpal-story-critic  (re-review, final verdict)|
        |                                             |
        +-- AI_APPROVED ------------------------------+
        |
        +-- NEEDS_HUMAN --------------------------+
                                                    |
                                                    v
                                      HUMAN APPROVAL
                                                    |
                                                    v
pocketpal-implementer   (write code in worktree, run builds if native)
    |
    v
pocketpal-tester        (write/run tests in worktree)
    |
    v
pocketpal-pipeline-reviewer  (verify builds, quality gate)
    |
    v
DRAFT PR from feature branch
    |
    v
HUMAN REVIEW & MERGE
```

## Operating Rules

### Worktree Isolation

Every implementation, test, or PR review of PocketPal app code must happen in a
dedicated worktree under `worktrees/`. The `repos/pocketpal-ai/` submodule is
only the source used to create worktrees and read source code.

Agents must stop and report instead of proceeding when:
- `pwd` is inside `repos/pocketpal-ai/`
- the current branch is `main` or `master`
- expected `WORKTREE`, `BRANCH`, or story context is missing for pipeline work
- a requested action would mutate, build, or commit inside the submodule

### Submodule Read-Only

`repos/pocketpal-ai/` is read-only with no exceptions.

Agents must never:
- edit files in `repos/pocketpal-ai/`
- switch branches, commit, merge, rebase, or stash inside `repos/pocketpal-ai/`
- run builds, tests, E2E specs, or package installs from the submodule
- reference submodule build artifacts in environment variables or reports
- upload or commit submodule files as generated assets

If a task needs a build, test run, screenshot, or report, create or reuse a
worktree and produce the artifact there.

### Story Gate

Implementation work requires a story file in `workflows/stories/`. Do not
implement directly from ad hoc plans.

### Native Verification

When a story or diff touches native dependencies or native code, mark it
`NATIVE_CHANGES=YES`. Before calling the work ready, run:
- `pod install`
- an iOS build
- an Android build

Missing native verification is a blocking review issue unless the user
explicitly changes the requirement.

### Secrets And Config

Do not read, copy, or bulk-sync `.env` files or private config by hand. Use only
the allowlisted sync behavior in `./tools/create-worktree.sh` or
`./tools/sync-worktree-config.sh`.

### Cleanup

Never remove worktrees with raw `git worktree remove`, `git worktree prune`,
`rm -r`, `rm -rf`, `rmdir`, or Finder/manual deletion. Use
`./tools/remove-worktree.sh <name> --yes` only when the user explicitly asks for
cleanup.

## Request Handling

### Implement This Feature

1. Create or identify a task worktree.
2. Create or update a story file in `workflows/stories/`.
3. Keep implementation inside the worktree only.
4. Run tests and required native verification.
5. Leave cleanup alone unless the user asked for it.

### Review This PR

1. Use a dedicated PR worktree such as `PR-<n>` or `PR-<n>-e2e`.
2. Do not reuse or delete unrelated task worktrees.
3. Review against the story, project patterns, tests, and native requirements.

## GitHub Conventions

**Signature** - include at the end of all GitHub content such as PRs, issues,
and comments:

```text
Generated by [PocketPal Dev Team](https://github.com/a-ghorbani/pocketpal-dev-team)
```

**Git commits** - never add `Co-Authored-By` trailers. Enforced by hook.

**Title formats:**

| Type | Format | Label |
|------|--------|-------|
| Bug | `[Bug]: <description>` | `bug` |
| Feature | `[Feat]: <description>` | `enhancement` |
| PR | Short description under 70 chars | - |

## Commands

### Create a task worktree

```bash
./tools/create-worktree.sh TASK-YYYYMMDD-HHMM
```

Defaults:
- worktree: `worktrees/TASK-...`
- branch: `feature/TASK-...`
- base ref: `origin/main`

### Create a custom worktree

```bash
# PR branch after fetch
./tools/create-worktree.sh PR-490 --branch pr-490 --ref pr-490

# Detached E2E worktree from an existing remote branch ref
./tools/create-worktree.sh PR-490-e2e --detach --ref origin/my-pr-branch
```

The custom examples assume the requested ref already exists locally or on
`origin`. For PR reviews, fetch the PR branch first, then create the worktree.

### Sync allowlisted config into an existing worktree

```bash
./tools/sync-worktree-config.sh ./worktrees/TASK-YYYYMMDD-HHMM
```

### Remove a worktree deliberately

```bash
./tools/remove-worktree.sh TASK-YYYYMMDD-HHMM --yes
./tools/remove-worktree.sh TASK-YYYYMMDD-HHMM --yes --force
```

## Naming Conventions

| Type | Worktree | Branch | Story File |
|------|----------|--------|------------|
| New task | `worktrees/TASK-YYYYMMDD-HHMM` | `feature/TASK-YYYYMMDD-HHMM` | `TASK-YYYYMMDD-HHMM.md` |
| PR fix | `worktrees/PR-<number>` | `pr-<number>` | `PR-<number>-fix.md` |
| PR E2E | `worktrees/PR-<number>-e2e` | detached | n/a |

## Key References

- `templates/story-template.md`
- `context/patterns.md`
- `context/pocketpal-overview.md`
- `docs/standards/code-review.md`
- `docs/workflows/visual-capture.md`
