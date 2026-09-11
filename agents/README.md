# Agent roles

One file per role: `agents/<name>.md`. It is the only copy, so edit it directly.

Its frontmatter carries every harness's keys: `name`, `description`, `disallowedTools` (Claude Code), and `mode` / `permission` (opencode). Each harness ignores the others' keys. `.claude/agents/` and `.opencode/agents/` are symlinks to these files. Codex reads only TOML, so `.codex/agents/<name>.toml` is a stub that tells Codex to read this file.

Codex limits, from its source (`codex-rs/agent-roles`, `core/src/agent/role.rs`, v0.153.4):
- A role file needs `name`, `description`, and `developer_instructions`, and unknown keys are rejected. There is no instructions-from-file key (`model_instructions_file` replaces Codex's whole system prompt), which is why the stub points at the file.
- A role applies only instructions, model/reasoning settings, and feature or skill *disables*. `sandbox_mode` and permissions always come from the parent session, and a role cannot disable spawning. So "roles are leaves" is an instruction in Codex, not an enforced rule.

Run `tools/sync-harness.py` after adding, renaming, or removing a role, or after changing its description.
