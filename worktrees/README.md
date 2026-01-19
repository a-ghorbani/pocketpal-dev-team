# Worktrees

Git worktrees of pocketpal-ai for parallel development.

Each subdirectory is a separate branch checkout.

## Create a worktree

```bash
cd /Users/aghorbani/codes/pocketpal-ai
git worktree add ../pocketpal-dev-team/worktrees/feature-123 -b feature/issue-123
```

## List worktrees

```bash
git worktree list
```

## Remove a worktree

```bash
git worktree remove ../pocketpal-dev-team/worktrees/feature-123
```
