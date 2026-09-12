# Vendored from pi

`index.ts`, `agents.ts` and `README.md` are copied verbatim from pi's own example
extension, MIT licensed:

    @earendil-works/pi-coding-agent@0.85.1 → examples/extensions/subagent/

The sample `agents/` directory is deliberately not copied; our roles come from
`.pi/agents/`, which `tools/sync-harness.py` links to `agents/<name>.md`.

Why vendored rather than referenced: the installed path is machine-specific, and
`pi -e <directory>` silently loads nothing (only an explicit entry file works),
so a committed copy with an explicit path in `.pi/settings.json` is the form that
survives a fresh clone.

To refresh after a pi upgrade, copy those three files again from the new version
and re-run the guard and dispatch checks in `docs/workflows/pipeline.md`.
