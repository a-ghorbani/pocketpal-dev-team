---
name: review-l10n
description: Review a Weblate auto-merge PR (or any locale PR) for PocketPal. Computes per-locale completion, identifies wirable candidates, runs per-language semantic review via subagents, validates placeholders, and optionally applies fixes back to Weblate (overwrites + suggestions + comments).
user-invocable: true
argument-hint: "<pr-number | branch-ref | locales-dir>"
---

@skills/review-l10n/SKILL.md

Target: $ARGUMENTS
