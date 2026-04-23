# Codex Setup

Codex should follow [AGENTS.md](./AGENTS.md) as the repo-level operating
contract.

Important difference from Claude Code: the rules in `.claude/settings.json` and
the hook scripts are not automatically enforced just because they exist. When
working through Codex, follow `AGENTS.md` explicitly and use the helper scripts
in `tools/` instead of raw worktree lifecycle commands.
