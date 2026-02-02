---
name: review-pr
description: Review an external PR for PocketPal AI. Analyzes code quality, l10n, testing patterns, and architecture compliance.
user-invocable: true
argument-hint: "[pr-number]"
---

# Review PR Workflow

You are starting a PR review workflow for PocketPal AI.

## Input
PR Number: $ARGUMENTS

## Instructions

Use the `pocketpal-pr-reviewer` agent to analyze this PR.

```
Use pocketpal-pr-reviewer to review PR #$ARGUMENTS

Repository: ./repos/pocketpal-ai
```

The pr-reviewer will:
1. Create a worktree at `worktrees/PR-$ARGUMENTS`
2. Fetch the PR branch
3. Analyze for:
   - L10n completeness (en, ja, zh in src/utils/l10n.ts)
   - Testing patterns (no inline store mocks, use jest/test-utils)
   - Architecture compliance (MobX patterns, component structure)
   - Code quality (lint, typecheck, tests)
   - Security issues
4. Produce a review report with:
   - Issues categorized by severity
   - Option A: GitHub comments for author
   - Option B: Command to fix internally via orchestrator

## After Review

If issues need to be fixed internally, the reviewer will provide a command like:
```
claude "Use pocketpal-orchestrator: Fix issues in PR #$ARGUMENTS
Issues to fix:
1. ...
2. ...
"
```
