---
description: repos/pocketpal-ai/ is read-only — never modify, build, or reference artifacts from it
---

# Submodule is READ-ONLY — No Exceptions

`repos/pocketpal-ai/` is **only for reading source code and creating worktrees**.

Multiple agents run in parallel and all create worktrees from this submodule. Any direct modification (file edits, branch switches, commits) would corrupt the shared reference and break all other agents.

Agents must NEVER:
- **Reference submodule build artifacts** (e.g., `repos/pocketpal-ai/ios/build/...` as `E2E_APP_PATH`)
- **Run builds, tests, or E2E specs** from/against the submodule
- **Use submodule paths in env vars** pointing to outputs (builds, screenshots, reports)
- **Upload or commit submodule files** as assets

**If a worktree needs a build, build it IN the worktree.**
