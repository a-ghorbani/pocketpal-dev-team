---
description: Safety guarantees and system-level protections for all agents
---

# Safety Guarantees

## Agent Pre-Flight Checks

Every agent has hard stops that prevent critical mistakes:

| Protection | Enforcement |
|------------|-------------|
| **Worktree Isolation** | Pre-flight check: `pwd` must contain `worktrees/TASK-` |
| **Branch Protection** | Pre-flight check: branch must NOT be `main` or `master` |
| **Native Build Verification** | `NATIVE_CHANGES=YES` triggers mandatory `pod install` + builds |
| **Context Passing** | Agents refuse to work without `WORKTREE` and `BRANCH` params |

If any pre-flight check fails, agents STOP and report the error.

## System-Level Protections (Hooks & Permissions)

Enforced by `.claude/settings.json`:

| Protection | Mechanism |
|------------|-----------|
| **Block commits to main** | Hook: `tools/block-commit-to-main.sh` |
| **Submodule read-only** | Hook: `tools/guard-submodule-edit.sh` blocks Edit/Write to `repos/pocketpal-ai/` |
| **Submodule git guard** | Hook: `tools/guard-submodule-git.sh` blocks mutating git commands in `repos/pocketpal-ai/` |
| **Path-scoped edits** | Permission: Edit/Write denied for `repos/pocketpal-ai/**`, allowed in `worktrees/**` |
| **Block force push** | Permission: Denies `git push -f` and `git push origin main` |
| **Secrets protection** | Permission: Denies Read/Edit of `.env` files |
