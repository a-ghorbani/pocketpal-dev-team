# E2E spec catalog

Read from `skills/run-e2e/SKILL.md` when picking a spec.

## Core (`e2e/specs/*.spec.ts`)

| Spec | Tests | Use when |
|---|---|---|
| `quick-smoke` | Full user journey on the smallest model (SmolLM2-135M): drawer → Models → HF search → download → load → chat → assert tokens/sec timing. | Default sanity gate. First thing to run before anything more targeted. |
| `load-stress` | Multiple load/unload cycles with inference between each. Per-model via `TEST_MODELS`. | Reproducing or guarding against crashes on model reload. |
| `benchmark-matrix` | Drives the in-app `BenchmarkRunnerScreen` across `{models} × {quants} × {backends}`; writes canonical JSON via the automation bridge. Android-only, requires the `e2e` flavor APK. | Perf regression sweeps; producing a report for `scripts/benchmark-compare.ts`. |
| `memory-profile` | Captures memory at 7 lifecycle checkpoints (app_launch → models_screen → chat_screen → model_loaded → chat_active → post_chat_idle → model_unloaded); writes canonical JSON for the `/memory-profile` pipeline. | Memory regression sweeps; producing a report for `scripts/memory-compare.ts`. |
| `visual-capture` | Parametrised screenshot generator driven by the `VISUAL_CAPTURES` env var. Skips silently if the var is unset — it is not a regression test. | Producing PR screenshots from a story file (`docs/workflows/visual-capture.md`). |
| `diagnostic` | Dumps Appium page-source XML to `e2e/debug-output/` at each navigation step. Not a regression test. | Debugging "no such element" failures by inspecting what Appium actually sees. |

## Feature (`e2e/specs/features/*.spec.ts`)

`quick-smoke` already covers the core chat path. Run a feature spec instead when the change is localised to that feature.

| Spec | Tests | Use when |
|---|---|---|
| `thinking` | Loads qwen3-0.6b, toggles thinking, asserts the "Reasoning" bubble appears and disappears. | Touching the thinking toggle, reasoning bubble, or thinking-capable inference path. |
| `language` | Cycles every supported language, asserts the UI updates. No model load required. | l10n changes, language switcher, `src/locales/` work. |
| `draft-autosave` | Asserts unsent input text persists across session switches and clears on send. | Changes to chat input draft persistence or session-switch behaviour. |
| `remote-server` | Adds a remote OpenAI-compatible model from the Models FAB, chats with it, deletes the server. Requires a reachable OpenAI-compatible server. | Remote-model / remote-server changes. |
| `talent-tool-use` | Creates a Pal with `render_html` enabled, sends a prompt, asserts the HTML preview bubble appears. Uses Qwen3-1.7B with temperature=0/seed=1 for determinism. | Talent registry, tool-use plumbing, HTML preview surface. |
