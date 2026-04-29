---
name: review-pr
description: Review an external PocketPal PR or code change using the shared review standard.
---

# Review PR

External PR/code review entry point.

## Input

A PR number, branch ref, or worktree path. `/review-pr`:

```text
/review-pr <pr-number>
```

## What this skill does

Delegate to the PocketPal code reviewer agent `pocketpal-code-reviewer` with `target_type: pr`. The agent handles all three target types;
