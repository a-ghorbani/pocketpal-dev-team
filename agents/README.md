# Agent roles

One file per role: `agents/<name>.md`, frontmatter `name` + `description`, body = the role's instructions. These are the only files to edit.

`tools/sync-harness.py` generates the per-harness copies (`.claude/agents/`, `.codex/agents/*.toml`, `.opencode/agents/`). Keep harness-specific keys (tools, models, permissions) out of these sources; the generator adds them.
