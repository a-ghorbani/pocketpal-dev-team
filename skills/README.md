# Skills

One directory per skill: `skills/<name>/SKILL.md` in the Agent Skills format (`name` must equal the directory; always set it, opencode drops skills without one). These are the only skill files to edit.

The skill directory is the only copy. `tools/sync-harness.py` symlinks each skill into `.claude/skills/` (Claude Code) and `.agents/skills/` (Codex, opencode). Claude-only frontmatter such as `user-invocable` and `argument-hint` is ignored elsewhere.
