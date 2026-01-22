# Worktrees

Git worktrees of pocketpal-ai for parallel development.

Each subdirectory is a separate branch checkout.

**IMPORTANT**: All worktree commands must be run from `/Users/aghorbani/codes/pocketpal-ai` (the source repo), NOT from pocketpal-dev-team.

## Create a worktree

```bash
cd /Users/aghorbani/codes/pocketpal-ai
git worktree add ../pocketpal-dev-team/worktrees/TASK-YYYYMMDD-HHMM -b feature/TASK-YYYYMMDD-HHMM
```

## List worktrees

```bash
cd /Users/aghorbani/codes/pocketpal-ai
git worktree list
```

## Remove a worktree (after PR merged)

```bash
cd /Users/aghorbani/codes/pocketpal-ai
git worktree remove ../pocketpal-dev-team/worktrees/TASK-YYYYMMDD-HHMM
```

## Clean up stale worktrees

If a worktree directory was deleted manually without using `git worktree remove`:

```bash
cd /Users/aghorbani/codes/pocketpal-ai
git worktree prune
```
