# Agent Instructions

This repo is the workflow control plane for PocketPal AI. The target app code
is in `repos/pocketpal-ai`, but that submodule is read-only. Treat this file as
the high-signal contract for any coding agent working here.

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

## Safe Entry Points

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
./tools/create-worktree.sh PR-490 --branch pr-490 --ref pr-490
./tools/create-worktree.sh PR-490-e2e --detach --ref origin/my-pr-branch
```

### Sync allowlisted config into an existing worktree

```bash
./tools/sync-worktree-config.sh ./worktrees/TASK-YYYYMMDD-HHMM
```

### Remove a worktree deliberately

```bash
./tools/remove-worktree.sh TASK-YYYYMMDD-HHMM --yes
./tools/remove-worktree.sh TASK-YYYYMMDD-HHMM --yes --force
```

## Expected Workflow By Request Type

### "Implement this feature"

1. Create or identify a task worktree.
2. Create or update a story file in `workflows/stories/`.
3. Keep implementation inside the worktree only.
4. Run tests and required native verification.
5. Leave cleanup alone unless the user asked for it.

### "Review this PR"

1. Use a dedicated PR worktree such as `PR-<n>` or `PR-<n>-e2e`.
2. Do not reuse or delete unrelated task worktrees.
3. Review against the story, project patterns, tests, and native requirements.

## Key References

- `CLAUDE.md`
- `templates/story-template.md`
- `context/patterns.md`
- `.claude/rules/submodule-readonly.md`
- `.claude/settings.json`
