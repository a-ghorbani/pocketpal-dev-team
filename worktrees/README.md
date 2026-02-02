# Worktrees

Git worktrees of pocketpal-ai for parallel development.

Each subdirectory is a separate branch checkout.

**IMPORTANT**: All worktree commands must be run from `repos/pocketpal-ai` (the submodule), NOT from pocketpal-dev-team root.

## Create a worktree

```bash
cd repos/pocketpal-ai
git worktree add ../../worktrees/TASK-YYYYMMDD-HHMM -b feature/TASK-YYYYMMDD-HHMM
```

## List worktrees

```bash
cd repos/pocketpal-ai
git worktree list
```

## Remove a worktree (after PR merged)

```bash
cd repos/pocketpal-ai
git worktree remove ../../worktrees/TASK-YYYYMMDD-HHMM
```

## Clean up stale worktrees

If a worktree directory was deleted manually without using `git worktree remove`:

```bash
cd repos/pocketpal-ai
git worktree prune
```
