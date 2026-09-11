# Agent roles

One file per role: `agents/<name>.md`. It is the only copy, so edit it directly.

Its frontmatter carries every harness's keys: `name`, `description`, `disallowedTools` (Claude Code), and `mode` / `permission` (opencode). Each harness ignores the others' keys. `.claude/agents/` and `.opencode/agents/` are symlinks to these files. Codex reads only TOML, so `.codex/agents/<name>.toml` is a stub that tells Codex to read this file.

Run `tools/sync-harness.py` after adding, renaming, or removing a role, or after changing its description.
