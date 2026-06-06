# Closed — superseded

This story is closed. The context-full warning UX shipped via a separate
implementation from `TASK-20260605-1715`, which was merged to `main`.

Why the rebuild won:

- Single global `n_ctx` from the start (no per-session override layer added
  and removed mid-flight).
- Single `used` field on the snapshot, computed once at the completion
  boundary; readers don't recompute.
- No `pendingReloadDiff` / Settings-mismatch surface — the entire phantom-diff
  bug class (clamp + default normalisation mismatches between
  `getEffectiveContextInitParams` and `createContextInitParams`) is impossible
  by construction.
- Reload rollback restores prior `n_ctx` AND re-inits the model, so failure
  doesn't leave the chat with no loaded context.

Artefacts kept for reference:

- `intent-brief.md` — original problem statement (still valid).
- `what.md` — design history including Amendment 4 (override-layer removal),
  preserved as a record of the design pivot that ultimately led to the
  rebuild.
- `how.md`, `deliberation-log.md` — implementation plan + deliberation rounds
  for the original approach.

PR #748 (the original implementation) was abandoned in draft.
