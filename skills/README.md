# Shared Skill Sources

This directory contains tool-agnostic skill source material.

Runtime-specific adapters live in tool-owned discovery paths such as `.claude/skills/` and `.codex/skills/`. Adapters may import these shared sources when include behavior is verified, or inline generated content as a fallback.

Root `skills/` is shared source only. It is not assumed to be a runtime discovery path.
