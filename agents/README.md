# Shared Agent Sources

This directory contains tool-agnostic agent role source material.

Runtime-specific adapters live in tool-owned locations such as `.claude/agents/`. Adapters may import these shared sources when the tool's include behavior is verified, or they may inline generated content as a documented fallback.

Do not put tool permission syntax, model names, or runtime-only frontmatter in shared agent sources.
